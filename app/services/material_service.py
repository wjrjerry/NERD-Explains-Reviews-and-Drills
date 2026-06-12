from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.user import User
from app.repositories.material_repository import MaterialRepository
from app.services.study_target_service import StudyTargetService


class MaterialService:
    """资料业务服务。

    负责资料上传校验、文件落盘、资料元数据入库，以及资料查询、预览和删除。
    """

    allowed_extensions = {
        ".pdf": MaterialType.pdf,
        ".txt": MaterialType.txt,
        ".png": MaterialType.image,
        ".jpg": MaterialType.image,
        ".jpeg": MaterialType.image,
        ".webp": MaterialType.image,
    }

    @staticmethod
    def _detect_file_type(filename: str) -> MaterialType:
        """根据文件扩展名识别资料类型。"""
        suffix = Path(filename).suffix.lower()
        file_type = MaterialService.allowed_extensions.get(suffix)
        if file_type is None:
            raise ValueError("仅支持上传 PDF、TXT 和图片资料")

        return file_type

    @staticmethod
    async def _read_upload_file(file: UploadFile) -> bytes:
        """读取上传文件内容并校验文件大小。"""
        content = await file.read()
        max_size = settings.max_upload_size_mb * 1024 * 1024

        if len(content) == 0:
            raise ValueError("上传文件不能为空")

        if len(content) > max_size:
            raise ValueError(f"文件大小不能超过 {settings.max_upload_size_mb} MB")

        return content

    @staticmethod
    def _build_stored_filename(original_filename: str) -> str:
        """生成服务端保存文件名。

        使用 UUID 避免不同用户上传同名文件时互相覆盖。
        """
        suffix = Path(original_filename).suffix.lower()
        return f"{uuid4().hex}{suffix}"

    @staticmethod
    def _save_file(content: bytes, stored_filename: str) -> Path:
        """保存文件到本地上传目录。"""
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / stored_filename
        file_path.write_bytes(content)

        return file_path

    @staticmethod
    async def upload(
        db: AsyncSession,
        *,
        current_user: User,
        target_id: int,
        file: UploadFile,
    ) -> Material:
        """上传资料。

        上传流程：
        1. 校验课程/考试目标是否属于当前用户。
        2. 校验文件类型是否为 PDF、TXT 或图片。
        3. 校验文件大小是否超过系统限制。
        4. 保存文件到上传目录。
        5. 创建资料元数据记录，解析状态初始为 uploaded。
        """
        await StudyTargetService.get_detail(
            db,
            current_user=current_user,
            target_id=target_id,
        )

        if not file.filename:
            raise ValueError("上传文件名不能为空")

        file_type = MaterialService._detect_file_type(file.filename)
        content = await MaterialService._read_upload_file(file)
        stored_filename = MaterialService._build_stored_filename(file.filename)
        file_path = MaterialService._save_file(content, stored_filename)

        material = Material(
            user_id=current_user.id,
            target_id=target_id,
            original_filename=file.filename,
            stored_filename=stored_filename,
            file_path=str(file_path),
            file_type=file_type,
            content_type=file.content_type,
            file_size=len(content),
            parse_status=MaterialParseStatus.uploaded,
        )

        return await MaterialRepository.create(db, material)

    @staticmethod
    async def list_by_current_user(
        db: AsyncSession,
        *,
        current_user: User,
        page: int,
        page_size: int,
        target_id: int | None = None,
    ) -> tuple[list[Material], int]:
        """分页查询当前用户的资料列表。"""
        return await MaterialRepository.list_by_user(
            db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            target_id=target_id,
        )

    @staticmethod
    async def get_detail(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> Material:
        """获取当前用户的资料详情。"""
        material = await MaterialRepository.get_by_id(
            db,
            material_id=material_id,
            user_id=current_user.id,
        )
        if material is None:
            raise ValueError("资料不存在")

        return material

    @staticmethod
    async def preview(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> tuple[Material, str | None, str]:
        """预览资料。

        第一阶段只直接读取 TXT 文件内容；PDF 和图片预览先返回明确提示。
        """
        material = await MaterialService.get_detail(
            db,
            current_user=current_user,
            material_id=material_id,
        )

        if material.file_type != MaterialType.txt:
            return material, None, "当前阶段仅支持 TXT 资料文本预览"

        file_path = Path(material.file_path)
        if not file_path.exists():
            raise ValueError("资料文件不存在")

        preview_text = file_path.read_text(encoding="utf-8", errors="ignore")
        return material, preview_text, "success"

    @staticmethod
    async def get_parsed_material(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> Material:
        """获取当前用户已解析完成的资料。

        AI 知识提炼、问答和出题模块应通过该方法读取资料文本。
        """
        material = await MaterialService.get_detail(
            db,
            current_user=current_user,
            material_id=material_id,
        )

        if material.parse_status != MaterialParseStatus.parsed:
            raise ValueError("资料未解析完成")

        if not material.parsed_text:
            raise ValueError("资料解析文本为空")

        return material

    @staticmethod
    async def delete(
        db: AsyncSession,
        *,
        current_user: User,
        material_id: int,
    ) -> Material:
        """软删除当前用户的资料。

        当前阶段仅标记数据库记录为删除，不立即删除磁盘文件，便于后续排查问题。
        """
        material = await MaterialService.get_detail(
            db,
            current_user=current_user,
            material_id=material_id,
        )

        return await MaterialRepository.soft_delete(db, material)