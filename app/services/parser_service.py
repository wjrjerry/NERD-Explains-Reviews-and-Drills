import json
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession
from pypdf import PdfReader

import app.db.session as db_session
from app.core.config import settings
from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.parse_task import ParseTask
from app.models.user import User
from app.repositories.material_repository import MaterialRepository
from app.services import knowledge_service
from app.repositories.parse_task_repository import ParseTaskRepository
from app.repositories.user_repository import UserRepository
from app.services.material_service import MaterialService
from app.services.material_structure_service import MaterialStructureService
from app.services.vision_parse_service import VisionParseService, VisionParseServiceError


@dataclass
class ExtractResult:
    """资料解析结果和过程信息。"""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ParseFailure(ValueError):
    """带解析过程信息的失败异常。"""

    def __init__(
        self,
        message: str,
        *,
        metadata: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = metadata or {}
        self.warnings = warnings or []


class ParserService:
    """资料解析服务。

    负责根据资料类型提取文本，并将解析结果写回 materials 表。
    TXT 执行真实文本读取，PDF 优先执行文本提取，扫描版 PDF 和图片通过
    Tesseract OCR 提取文字。
    """

    max_parse_error_length = 500
    common_text_pattern = re.compile(
        r"[\w\s\u4e00-\u9fff，。；：、“”‘’（）《》！？,.!?;:()\\[\\]{}<>+=\\-*/%°^√≈≤≥≠|]"
    )

    @staticmethod
    def _ensure_file_exists(material: Material) -> Path:
        """校验资料文件是否存在。"""
        file_path = Path(material.file_path)
        if not file_path.exists():
            raise ValueError("资料文件不存在")

        return file_path

    @staticmethod
    def _extract_txt(material: Material) -> ExtractResult:
        """提取 TXT 文件文本内容。"""
        start_time = time.perf_counter()
        file_path = ParserService._ensure_file_exists(material)

        text = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).strip()

        if not text:
            raise ValueError("TXT 文件内容为空")

        return ParserService._finalize_extract_result(
            ExtractResult(
                text=text,
                metadata={
                    "method": "txt",
                    "page_count": 1,
                    "pages": [
                        {
                            "page_number": 1,
                            "method": "txt",
                            "status": "succeeded",
                            "char_count": len(text),
                        }
                    ],
                    "elapsed_ms": ParserService._elapsed_ms(start_time),
                },
            )
        )

    @staticmethod
    def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
        """执行 OCR 前的轻量图片预处理。

        包含 EXIF 方向纠正、灰度化、放大、自动对比度和二值化。这里仍保持
        轻量，避免引入 OpenCV 等较重依赖。
        """
        image = ImageOps.exif_transpose(image)
        image = image.convert("L")

        if settings.ocr_image_scale > 1:
            width, height = image.size
            image = image.resize(
                (
                    max(1, int(width * settings.ocr_image_scale)),
                    max(1, int(height * settings.ocr_image_scale)),
                )
            )

        image = ImageOps.autocontrast(image)
        threshold = min(255, max(0, settings.ocr_binarize_threshold))
        return image.point(lambda pixel: 255 if pixel > threshold else 0)

    @staticmethod
    def _run_ocr_on_image(image: Image.Image, *, context: str) -> tuple[str, dict[str, Any], list[str]]:
        """对单张图片执行 OCR，并返回清理后的文本。

        context 用于生成更明确的错误提示，例如“图片 OCR”或“PDF 第 1 页 OCR”。
        """
        start_time = time.perf_counter()
        try:
            prepared_image = ParserService._prepare_image_for_ocr(image)
            text = pytesseract.image_to_string(
                prepared_image,
                lang=settings.ocr_languages,
                timeout=settings.ocr_timeout_seconds,
            )
        except Exception as exc:
            raise ValueError(f"{context} 识别失败：{exc}") from exc

        text = text.strip()
        metadata = {
            "method": "ocr",
            "status": "succeeded",
            "char_count": len(text),
            "elapsed_ms": ParserService._elapsed_ms(start_time),
            "languages": settings.ocr_languages,
        }
        return text, metadata, ParserService._quality_warnings(text, context=context)

    @staticmethod
    def _extract_pdf_text(material: Material) -> ExtractResult:
        """使用 pypdf 提取文本型 PDF 内容。

        如果 PDF 本身包含可复制文本，该方法速度较快且结果更稳定；扫描版 PDF
        通常提取不到文本，会交给 OCR 兜底。
        """
        start_time = time.perf_counter()
        file_path = ParserService._ensure_file_exists(material)

        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            raise ValueError(f"PDF 文件读取失败：{exc}") from exc

        texts: list[str] = []
        pages: list[dict[str, Any]] = []

        for index, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                raise ValueError(f"PDF 第 {index} 页文本提取失败：{exc}") from exc

            page_text = page_text.strip()
            pages.append(
                {
                    "page_number": index,
                    "method": "pdf_text",
                    "status": "succeeded" if page_text else "empty",
                    "char_count": len(page_text),
                }
            )
            if page_text:
                texts.append(page_text)

        return ParserService._finalize_extract_result(
            ExtractResult(
                text="\n\n".join(texts).strip(),
                metadata={
                    "method": "pdf_text",
                    "page_count": len(reader.pages),
                    "pages": pages,
                    "elapsed_ms": ParserService._elapsed_ms(start_time),
                },
            )
        )

    @staticmethod
    def _extract_pdf_by_ocr(material: Material) -> ExtractResult:
        """将扫描版 PDF 转为图片后执行 OCR。

        这是 PDF 文本提取失败后的兜底路径，适合处理扫描版试卷、截图导出的
        PDF 等没有内嵌文本层的文件。
        """
        start_time = time.perf_counter()
        file_path = ParserService._ensure_file_exists(material)

        try:
            pages = convert_from_path(
                str(file_path),
                dpi=settings.pdf_ocr_dpi,
                first_page=1,
                last_page=settings.pdf_ocr_max_pages,
            )
        except Exception as exc:
            raise ValueError(f"PDF 转图片失败：{exc}") from exc

        texts: list[str] = []
        page_records: list[dict[str, Any]] = []
        warnings: list[str] = []
        failed_pages: list[int] = []

        for index, page in enumerate(pages, start=1):
            try:
                page_text, page_metadata, page_warnings = ParserService._run_ocr_on_image(
                    page,
                    context=f"PDF 第 {index} 页 OCR",
                )
            except ValueError as exc:
                failed_pages.append(index)
                page_records.append(
                    {
                        "page_number": index,
                        "method": "ocr",
                        "status": "failed",
                        "error": str(exc),
                    }
                )
                warnings.append(f"PDF 第 {index} 页 OCR 失败，已跳过该页")
                continue

            page_metadata["page_number"] = index
            page_metadata["status"] = "succeeded" if page_text else "empty"
            page_records.append(page_metadata)
            warnings.extend(page_warnings)
            if page_text:
                texts.append(page_text)

        parsed_text = "\n\n".join(texts).strip()

        if not parsed_text:
            raise ParseFailure(
                "PDF OCR 未识别到可用文本，可能是扫描质量较低或不包含文字",
                metadata={
                    "method": "pdf_ocr",
                    "page_count": len(pages),
                    "pages": page_records,
                    "failed_pages": failed_pages,
                    "elapsed_ms": ParserService._elapsed_ms(start_time),
                    "dpi": settings.pdf_ocr_dpi,
                    "max_pages": settings.pdf_ocr_max_pages,
                    "saved_char_count": 0,
                },
                warnings=warnings,
            )

        metadata = {
            "method": "pdf_ocr",
            "page_count": len(pages),
            "pages": page_records,
            "failed_pages": failed_pages,
            "elapsed_ms": ParserService._elapsed_ms(start_time),
            "dpi": settings.pdf_ocr_dpi,
            "max_pages": settings.pdf_ocr_max_pages,
        }
        if len(pages) >= settings.pdf_ocr_max_pages:
            warnings.append(f"扫描版 PDF OCR 最多处理前 {settings.pdf_ocr_max_pages} 页")

        return ParserService._finalize_extract_result(
            ExtractResult(text=parsed_text, metadata=metadata, warnings=warnings)
        )

    @staticmethod
    def _vision_result_to_extract_result(
        *,
        text: str,
        method: str,
        page_count: int,
        pages: list[dict[str, Any]],
        start_time: float,
        warnings: list[str] | None = None,
    ) -> ExtractResult:
        return ParserService._finalize_extract_result(
            ExtractResult(
                text=text,
                metadata={
                    "method": method,
                    "page_count": page_count,
                    "pages": pages,
                    "elapsed_ms": ParserService._elapsed_ms(start_time),
                },
                warnings=warnings or [],
            )
        )

    @staticmethod
    def _extract_image_vision(material: Material) -> ExtractResult:
        """使用多模态视觉模型解析单张图片。

        该能力默认关闭；开启后主要作为 OCR 失败或 OCR 质量较差时的兜底。
        """
        start_time = time.perf_counter()
        file_path = ParserService._ensure_file_exists(material)
        vision_result = VisionParseService.parse_image_file(file_path, context="图片视觉解析")
        page_record = {
            "page_number": 1,
            "method": "vision",
            "status": "succeeded",
            "char_count": len(vision_result.text),
            **vision_result.metadata,
        }
        return ParserService._vision_result_to_extract_result(
            text=vision_result.text,
            method="image_vision",
            page_count=1,
            pages=[page_record],
            start_time=start_time,
            warnings=vision_result.warnings,
        )

    @staticmethod
    def _needs_vision(*, ocr_failed: bool = False, ocr_warnings: list[str] | None = None) -> bool:
        """判断当前资料页是否需要多模态视觉解析。"""
        if not settings.vision_enabled or not VisionParseService.is_enabled():
            return False

        if ocr_failed and settings.vision_fallback_on_ocr_failure:
            return True

        if ocr_warnings and settings.vision_fallback_on_low_quality:
            return True

        return False

    @staticmethod
    def _extract_pdf_by_vision(material: Material) -> ExtractResult:
        """将 PDF 页面转图片后交给多模态视觉模型解析。

        这条路径适合扫描版几何题、复杂 slides 或 OCR 完全失败的资料。默认
        关闭，避免在没有 API Key 时影响现有离线 OCR 流程。
        """
        start_time = time.perf_counter()
        file_path = ParserService._ensure_file_exists(material)

        try:
            pages = convert_from_path(
                str(file_path),
                dpi=settings.pdf_ocr_dpi,
                first_page=1,
                last_page=settings.vision_max_pages,
            )
        except Exception as exc:
            raise ValueError(f"PDF 转图片失败：{exc}") from exc

        texts: list[str] = []
        page_records: list[dict[str, Any]] = []
        warnings: list[str] = []
        failed_pages: list[int] = []

        with tempfile.TemporaryDirectory(prefix="material-vision-") as temp_dir:
            temp_path = Path(temp_dir)
            for index, page in enumerate(pages, start=1):
                page_path = temp_path / f"page-{index}.png"
                page.save(page_path, format="PNG")

                try:
                    vision_result = VisionParseService.parse_image_file(
                        page_path,
                        context=f"PDF 第 {index} 页视觉解析",
                    )
                except VisionParseServiceError as exc:
                    failed_pages.append(index)
                    page_records.append(
                        {
                            "page_number": index,
                            "method": "vision",
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                    warnings.append(f"PDF 第 {index} 页视觉解析失败，已跳过该页")
                    continue

                page_records.append(
                    {
                        "page_number": index,
                        "method": "vision",
                        "status": "succeeded",
                        "char_count": len(vision_result.text),
                        **vision_result.metadata,
                    }
                )
                warnings.extend(vision_result.warnings)
                texts.append(vision_result.text)

        parsed_text = "\n\n".join(texts).strip()
        if not parsed_text:
            raise ParseFailure(
                "PDF 视觉解析未识别到可用文本",
                metadata={
                    "method": "pdf_vision",
                    "page_count": len(pages),
                    "pages": page_records,
                    "failed_pages": failed_pages,
                    "elapsed_ms": ParserService._elapsed_ms(start_time),
                    "max_pages": settings.vision_max_pages,
                    "saved_char_count": 0,
                },
                warnings=warnings,
            )

        if len(pages) >= settings.vision_max_pages:
            warnings.append(f"PDF 视觉解析最多处理前 {settings.vision_max_pages} 页")

        result = ParserService._vision_result_to_extract_result(
            text=parsed_text,
            method="pdf_vision",
            page_count=len(pages),
            pages=page_records,
            start_time=start_time,
            warnings=warnings,
        )
        result.metadata["failed_pages"] = failed_pages
        result.metadata["max_pages"] = settings.vision_max_pages
        return result

    @staticmethod
    def _extract_pdf(material: Material) -> ExtractResult:
        """提取 PDF 文件文本。

        优先使用 pypdf 提取文本型 PDF；如果没有提取到可用文本，则将 PDF
        页面转为图片并通过 OCR 兜底。
        """
        pdf_text_result = ParserService._extract_pdf_text(material)

        if pdf_text_result.text:
            return pdf_text_result

        try:
            return ParserService._extract_pdf_by_ocr(material)
        except ParseFailure:
            if ParserService._needs_vision(ocr_failed=True):
                return ParserService._extract_pdf_by_vision(material)
            raise

    @staticmethod
    def _extract_image_ocr(material: Material) -> ExtractResult:
        """使用 Tesseract OCR 提取图片文字。

        支持简体中文和英文混合识别。识别为空时返回明确错误，便于前端展示
        “图片过于模糊或不含文字”等提示。
        """
        start_time = time.perf_counter()
        file_path = ParserService._ensure_file_exists(material)

        try:
            with Image.open(file_path) as image:
                text, page_metadata, warnings = ParserService._run_ocr_on_image(image, context="图片 OCR")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"图片文件读取失败：{exc}") from exc

        if not text:
            page_metadata["status"] = "empty"
            raise ParseFailure(
                "图片 OCR 未识别到可用文本，请确认图片清晰且包含文字",
                metadata={
                    "method": "image_ocr",
                    "page_count": 1,
                    "pages": [page_metadata],
                    "elapsed_ms": ParserService._elapsed_ms(start_time),
                    "saved_char_count": 0,
                },
                warnings=warnings,
            )

        page_metadata["page_number"] = 1
        return ParserService._finalize_extract_result(
            ExtractResult(
                text=text,
                metadata={
                    "method": "image_ocr",
                    "page_count": 1,
                    "pages": [page_metadata],
                    "elapsed_ms": ParserService._elapsed_ms(start_time),
                },
                warnings=warnings,
            )
        )

    @staticmethod
    def _extract_image(material: Material) -> ExtractResult:
        """提取图片文本。

        图片资料统一通过 OCR 进入 parsed_text，AI 模块后续仍只消费解析后的
        文本，不需要关心资料来自图片还是文本文件。
        """
        try:
            ocr_result = ParserService._extract_image_ocr(material)
        except (ParseFailure, ValueError) as ocr_exc:
            if ParserService._needs_vision(ocr_failed=True):
                try:
                    vision_result = ParserService._extract_image_vision(material)
                except VisionParseServiceError:
                    raise ocr_exc

                vision_result.warnings = [
                    f"图片 OCR 失败，已使用视觉模型兜底解析：{ocr_exc}",
                    *vision_result.warnings,
                ]
                return vision_result
            raise ocr_exc

        if ParserService._needs_vision(ocr_warnings=ocr_result.warnings):
            try:
                vision_result = ParserService._extract_image_vision(material)
            except VisionParseServiceError as exc:
                ocr_result.warnings.append(f"图片视觉解析兜底失败：{exc}")
                return ParserService._finalize_extract_result(ocr_result)

            vision_result.warnings = [
                "图片 OCR 质量较低，已使用视觉模型兜底解析",
                *vision_result.warnings,
            ]
            return vision_result

        return ocr_result

    @staticmethod
    def _normalize_parse_error(exc: Exception) -> str:
        """将解析异常整理成适合入库和前端展示的短错误信息。"""
        message = str(exc).strip() or "资料解析失败"
        if len(message) > ParserService.max_parse_error_length:
            return f"{message[:ParserService.max_parse_error_length]}..."

        return message

    @staticmethod
    def _extract_text(material: Material) -> ExtractResult:
        """根据资料类型提取文本。"""
        if material.file_type == MaterialType.txt:
            return ParserService._extract_txt(material)

        if material.file_type == MaterialType.pdf:
            return ParserService._extract_pdf(material)

        if material.file_type == MaterialType.image:
            return ParserService._extract_image(material)

        raise ValueError("不支持的资料类型")

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.perf_counter() - start_time) * 1000)

    @staticmethod
    def _bad_char_ratio(text: str) -> float:
        if not text:
            return 1.0

        bad_count = sum(1 for char in text if ParserService.common_text_pattern.fullmatch(char) is None)
        return bad_count / len(text)

    @staticmethod
    def _quality_warnings(text: str, *, context: str) -> list[str]:
        warnings: list[str] = []
        normalized = text.strip()

        if len(normalized) < settings.ocr_min_text_length:
            warnings.append(f"{context} 识别文本较短，可能需要人工校对或视觉解析")

        bad_ratio = ParserService._bad_char_ratio(normalized)
        if bad_ratio > settings.ocr_bad_char_ratio:
            warnings.append(f"{context} 疑似存在较多乱码，建议人工校对或视觉解析")

        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        if len(lines) >= 5 and sum(1 for line in lines if len(line) <= 3) / len(lines) > 0.5:
            warnings.append(f"{context} 文本碎片较多，可能是版面复杂或图片质量较低")

        return warnings

    @staticmethod
    def _finalize_extract_result(result: ExtractResult) -> ExtractResult:
        text = result.text.strip()
        original_char_count = len(text)
        warnings = list(dict.fromkeys(result.warnings))
        metadata = dict(result.metadata)

        if original_char_count > settings.parsed_text_max_chars:
            text = text[: settings.parsed_text_max_chars].rstrip()
            warnings.append(
                f"解析文本超过 {settings.parsed_text_max_chars} 字符，已截断后保存以避免 AI 输入过长"
            )
            metadata["truncated"] = True
            metadata["original_char_count"] = original_char_count

        metadata["saved_char_count"] = len(text)
        metadata["warnings_count"] = len(warnings)

        return ExtractResult(text=text, metadata=metadata, warnings=warnings)

    @staticmethod
    def _serialize_parse_metadata(metadata: dict[str, Any]) -> str:
        return json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _serialize_parse_warning(warnings: list[str]) -> str | None:
        unique_warnings = [warning for warning in dict.fromkeys(warnings) if warning]
        return "；".join(unique_warnings) if unique_warnings else None

    @staticmethod
    async def parse(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> Material:
        """解析资料并保存解析结果。

        解析流程：
        1. 校验资料是否属于当前用户。
        2. 将资料状态更新为 parsing。
        3. 根据资料类型提取文本。
        4. 成功时保存 parsed_text，并更新状态为 parsed。
        5. 失败时保存 parse_error，并更新状态为 failed。
        """
        material = await MaterialService.get_detail(
            db,
            current_user=current_user,
            material_id=material_id,
        )

        return await ParserService.parse_material(db, material=material)

    @staticmethod
    async def parse_material(
        db: AsyncSession,
        *,
        material: Material,
        task: ParseTask | None = None,
    ) -> Material:
        """解析指定资料记录。

        该方法要求调用方已经完成资料归属或管理员权限校验。普通用户接口通过
        parse() 先校验资料归属，管理员失败任务重试接口则在路由层完成管理员校验。
        """
        if task is not None:
            task = await ParseTaskRepository.mark_running(db, task)

        material = await MaterialRepository.update_parse_result(
            db,
            material,
            parse_status=MaterialParseStatus.parsing,
            parsed_text=None,
            parse_error=None,
            parse_warning=None,
            parse_metadata=None,
        )
        await MaterialStructureService.clear_for_material(db, material_id=material.id)

        try:
            extract_result = ParserService._extract_text(material)
            parsed_text = extract_result.text
            if not parsed_text.strip():
                raise ValueError("资料解析结果为空")

        except Exception as exc:
            parse_error = ParserService._normalize_parse_error(exc)
            parse_warning = None
            parse_metadata = None
            if isinstance(exc, ParseFailure):
                parse_warning = ParserService._serialize_parse_warning(exc.warnings)
                parse_metadata = ParserService._serialize_parse_metadata(exc.metadata)
            material = await MaterialRepository.update_parse_result(
                db,
                material,
                parse_status=MaterialParseStatus.failed,
                parsed_text=None,
                parse_error=parse_error,
                parse_warning=parse_warning,
                parse_metadata=parse_metadata,
            )
            if task is not None:
                await ParseTaskRepository.mark_failed(
                    db,
                    task,
                    failure_reason=parse_error,
                )

            return material

        material = await MaterialRepository.update_parse_result(
            db,
            material,
            parse_status=MaterialParseStatus.parsed,
            parsed_text=parsed_text,
            parse_error=None,
            parse_warning=ParserService._serialize_parse_warning(extract_result.warnings),
            parse_metadata=ParserService._serialize_parse_metadata(extract_result.metadata),
        )
        await MaterialStructureService.rebuild_for_material(db, material=material)
        if task is not None:
            await ParseTaskRepository.mark_succeeded(db, task)

        return material

    @staticmethod
    async def enqueue_material_parse(
        db: AsyncSession,
        *,
        material: Material,
    ) -> tuple[Material, ParseTask]:
        """创建解析任务，并将资料置为 parsing。

        该方法只负责入队和状态初始化，不执行耗时解析。真正的解析由
        parse_material_by_task_id() 在 BackgroundTasks 中完成。
        """
        task = await ParseTaskRepository.create(
            db,
            material_id=material.id,
            user_id=material.user_id,
        )
        material = await MaterialRepository.update_parse_result(
            db,
            material,
            parse_status=MaterialParseStatus.parsing,
            parsed_text=None,
            parse_error=None,
            parse_warning=None,
            parse_metadata=None,
        )

        return material, task

    @staticmethod
    async def parse_material_by_task_id(task_id: int) -> None:
        """后台解析任务入口。

        BackgroundTasks 在请求结束后运行，不能复用请求中的 AsyncSession。
        因此这里按 task_id 重新打开数据库会话、加载任务和资料，再执行解析。
        """
        async with db_session.AsyncSessionLocal() as db:
            task = await ParseTaskRepository.get_by_id(db, task_id)
            if task is None:
                return

            material = await MaterialRepository.get_by_id_for_admin(
                db,
                material_id=task.material_id,
            )
            if material is None:
                await ParseTaskRepository.mark_failed(
                    db,
                    task,
                    failure_reason="资料不存在",
                )
                return

            material = await ParserService.parse_material(db, material=material, task=task)
            user = await UserRepository.get_by_id(db, task.user_id)
            if user is not None:
                await knowledge_service.run_after_material_parsed(
                    db,
                    current_user=user,
                    material=material,
                )
