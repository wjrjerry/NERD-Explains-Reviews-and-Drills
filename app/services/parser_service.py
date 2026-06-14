from pathlib import Path

import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession
from pypdf import PdfReader

from app.db.session import AsyncSessionLocal
from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.parse_task import ParseTask
from app.models.user import User
from app.repositories.material_repository import MaterialRepository
from app.repositories.parse_task_repository import ParseTaskRepository
from app.services.material_service import MaterialService


class ParserService:
    """资料解析服务。

    负责根据资料类型提取文本，并将解析结果写回 materials 表。
    TXT 执行真实文本读取，PDF 优先执行文本提取，扫描版 PDF 和图片通过
    Tesseract OCR 提取文字。
    """

    ocr_languages = "chi_sim+eng"
    pdf_ocr_dpi = 200
    max_pdf_ocr_pages = 20
    max_parse_error_length = 500

    @staticmethod
    def _ensure_file_exists(material: Material) -> Path:
        """校验资料文件是否存在。"""
        file_path = Path(material.file_path)
        if not file_path.exists():
            raise ValueError("资料文件不存在")

        return file_path

    @staticmethod
    def _extract_txt(material: Material) -> str:
        """提取 TXT 文件文本内容。"""
        file_path = ParserService._ensure_file_exists(material)

        text = file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        ).strip()

        if not text:
            raise ValueError("TXT 文件内容为空")

        return text

    @staticmethod
    def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
        """执行 OCR 前的轻量图片预处理。

        转灰度可以减少颜色噪声，自动对比度能提升浅色文字和背景之间的区分度。
        这里保持处理轻量，避免为了 OCR 引入过重的图像处理流程。
        """
        image = image.convert("L")
        return ImageOps.autocontrast(image)

    @staticmethod
    def _run_ocr_on_image(image: Image.Image, *, context: str) -> str:
        """对单张图片执行 OCR，并返回清理后的文本。

        context 用于生成更明确的错误提示，例如“图片 OCR”或“PDF 第 1 页 OCR”。
        """
        try:
            prepared_image = ParserService._prepare_image_for_ocr(image)
            text = pytesseract.image_to_string(
                prepared_image,
                lang=ParserService.ocr_languages,
            )
        except Exception as exc:
            raise ValueError(f"{context} 识别失败：{exc}") from exc

        return text.strip()

    @staticmethod
    def _extract_pdf_text(material: Material) -> str:
        """使用 pypdf 提取文本型 PDF 内容。

        如果 PDF 本身包含可复制文本，该方法速度较快且结果更稳定；扫描版 PDF
        通常提取不到文本，会交给 OCR 兜底。
        """
        file_path = ParserService._ensure_file_exists(material)

        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            raise ValueError(f"PDF 文件读取失败：{exc}") from exc

        texts: list[str] = []

        for index, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                raise ValueError(f"PDF 第 {index} 页文本提取失败：{exc}") from exc

            page_text = page_text.strip()
            if page_text:
                texts.append(page_text)

        return "\n\n".join(texts).strip()

    @staticmethod
    def _extract_pdf_by_ocr(material: Material) -> str:
        """将扫描版 PDF 转为图片后执行 OCR。

        这是 PDF 文本提取失败后的兜底路径，适合处理扫描版试卷、截图导出的
        PDF 等没有内嵌文本层的文件。
        """
        file_path = ParserService._ensure_file_exists(material)

        try:
            pages = convert_from_path(
                str(file_path),
                dpi=ParserService.pdf_ocr_dpi,
                first_page=1,
                last_page=ParserService.max_pdf_ocr_pages,
            )
        except Exception as exc:
            raise ValueError(f"PDF 转图片失败：{exc}") from exc

        texts: list[str] = []

        for index, page in enumerate(pages, start=1):
            page_text = ParserService._run_ocr_on_image(
                page,
                context=f"PDF 第 {index} 页 OCR",
            )
            if page_text:
                texts.append(page_text)

        parsed_text = "\n\n".join(texts).strip()

        if not parsed_text:
            raise ValueError("PDF OCR 未识别到可用文本，可能是扫描质量较低或不包含文字")

        return parsed_text

    @staticmethod
    def _extract_pdf(material: Material) -> str:
        """提取 PDF 文件文本。

        优先使用 pypdf 提取文本型 PDF；如果没有提取到可用文本，则将 PDF
        页面转为图片并通过 OCR 兜底。
        """
        parsed_text = ParserService._extract_pdf_text(material)

        if parsed_text:
            return parsed_text

        return ParserService._extract_pdf_by_ocr(material)

    @staticmethod
    def _extract_image_ocr(material: Material) -> str:
        """使用 Tesseract OCR 提取图片文字。

        支持简体中文和英文混合识别。识别为空时返回明确错误，便于前端展示
        “图片过于模糊或不含文字”等提示。
        """
        file_path = ParserService._ensure_file_exists(material)

        try:
            with Image.open(file_path) as image:
                text = ParserService._run_ocr_on_image(image, context="图片 OCR")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"图片文件读取失败：{exc}") from exc

        if not text:
            raise ValueError("图片 OCR 未识别到可用文本，请确认图片清晰且包含文字")

        return text

    @staticmethod
    def _extract_image(material: Material) -> str:
        """提取图片文本。

        图片资料统一通过 OCR 进入 parsed_text，AI 模块后续仍只消费解析后的
        文本，不需要关心资料来自图片还是文本文件。
        """
        return ParserService._extract_image_ocr(material)

    @staticmethod
    def _normalize_parse_error(exc: Exception) -> str:
        """将解析异常整理成适合入库和前端展示的短错误信息。"""
        message = str(exc).strip() or "资料解析失败"
        if len(message) > ParserService.max_parse_error_length:
            return f"{message[:ParserService.max_parse_error_length]}..."

        return message

    @staticmethod
    def _extract_text(material: Material) -> str:
        """根据资料类型提取文本。"""
        if material.file_type == MaterialType.txt:
            return ParserService._extract_txt(material)

        if material.file_type == MaterialType.pdf:
            return ParserService._extract_pdf(material)

        if material.file_type == MaterialType.image:
            return ParserService._extract_image(material)

        raise ValueError("不支持的资料类型")

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
        )

        try:
            parsed_text = ParserService._extract_text(material)
            if not parsed_text.strip():
                raise ValueError("资料解析结果为空")

        except Exception as exc:
            parse_error = ParserService._normalize_parse_error(exc)
            material = await MaterialRepository.update_parse_result(
                db,
                material,
                parse_status=MaterialParseStatus.failed,
                parsed_text=None,
                parse_error=parse_error,
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
        )
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
        )

        return material, task

    @staticmethod
    async def parse_material_by_task_id(task_id: int) -> None:
        """后台解析任务入口。

        BackgroundTasks 在请求结束后运行，不能复用请求中的 AsyncSession。
        因此这里按 task_id 重新打开数据库会话、加载任务和资料，再执行解析。
        """
        async with AsyncSessionLocal() as db:
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

            await ParserService.parse_material(db, material=material, task=task)
