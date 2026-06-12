from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.user import User
from app.repositories.material_repository import MaterialRepository
from app.services.material_service import MaterialService


class ParserService:
    """资料解析服务。

    负责根据资料类型提取文本，并将解析结果写回 materials 表。
    当前真实支持 TXT 文本提取；PDF 和图片需要后续接入解析/OCR 后再开放。
    """

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

        return file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    @staticmethod
    def _extract_text(material: Material) -> str:
        """根据资料类型提取文本。"""
        if material.file_type == MaterialType.txt:
            return ParserService._extract_txt(material)

        if material.file_type == MaterialType.pdf:
            ParserService._ensure_file_exists(material)
            raise ValueError("当前仅支持 TXT 资料解析，PDF 解析尚未接入")

        if material.file_type == MaterialType.image:
            ParserService._ensure_file_exists(material)
            raise ValueError("当前仅支持 TXT 资料解析，图片 OCR 尚未接入")

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
            return await MaterialRepository.update_parse_result(
                db,
                material,
                parse_status=MaterialParseStatus.failed,
                parsed_text=None,
                parse_error=str(exc),
            )

        return await MaterialRepository.update_parse_result(
            db,
            material,
            parse_status=MaterialParseStatus.parsed,
            parsed_text=parsed_text,
            parse_error=None,
        )
