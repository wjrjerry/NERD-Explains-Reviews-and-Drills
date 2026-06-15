"""Shared material access helpers for member B's AI learning flow.

Member A owns the real materials module: upload, storage, parsing, OCR, and the
materials table. Before that module is complete, this file provides a small mock
material source so member B can develop knowledge extraction, QA, and question
generation against the same interface.

Important:
    Mock fallback is only allowed when the real materials table is not created
    yet. Other database errors should surface immediately, otherwise integration
    problems would be hidden behind mock data.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MaterialSnapshot:
    """Minimal material data needed by AI learning modules."""

    id: int
    user_id: int
    target_id: int | None
    parse_status: str
    title: str
    parsed_text: str


MOCK_MATERIALS: dict[int, MaterialSnapshot] = {
    1: MaterialSnapshot(
        id=1,
        user_id=1,
        target_id=1,
        parse_status="parsed",
        title="软件工程需求分析复习资料",
        parsed_text=(
            "需求分析用于明确系统边界、用户角色、功能范围和验收标准。"
            "数据流图用于描述输入、处理过程、数据存储和输出之间的关系。"
            "用例图用于表达学生、管理员等角色与系统功能之间的交互。"
            "AI知识提炼可以帮助学生从长篇资料中快速获得摘要、大纲、关键词、重点知识点和可能考点。"
        ),
    ),
    2: MaterialSnapshot(
        id=2,
        user_id=1,
        target_id=1,
        parse_status="parsing",
        title="正在解析的资料",
        parsed_text="",
    ),
    3: MaterialSnapshot(
        id=3,
        user_id=2,
        target_id=2,
        parse_status="parsed",
        title="其他用户的资料",
        parsed_text="这是另一个用户的资料，当前用户不能访问。",
    ),
}


def _is_missing_materials_table_error(exc: Exception) -> bool:
    """Return True only for the expected "materials table missing" case."""
    original = getattr(exc, "orig", exc)
    sqlstate = (
        getattr(original, "sqlstate", None)
        or getattr(original, "pgcode", None)
        or getattr(exc, "code", None)
    )
    if sqlstate == "42P01":
        return True

    message = str(exc).lower()
    return (
        "materials" in message
        and (
            "does not exist" in message
            or "undefinedtable" in message
            or "no such table" in message
        )
    )


def get_mock_material(
    material_id: int,
    *,
    user_id: int,
) -> MaterialSnapshot | None:
    """Return one mock material if it belongs to the current user.

    Mock IDs for local testing:
    - material_id=1, user_id=1: parsed material, should succeed.
    - material_id=2, user_id=1: parsing material, should return conflict.
    - material_id=3, user_id=1: belongs to another user, should behave as not found.
    """
    material = MOCK_MATERIALS.get(material_id)
    if material is None or material.user_id != user_id:
        return None
    return material


async def get_material_for_ai(
    db: Any,
    *,
    user_id: int,
    material_id: int,
) -> MaterialSnapshot | None:
    """Load material data for AI modules.

    The function first tries the real materials table. If and only if the table
    is not created yet, it falls back to MOCK_MATERIALS. SQL mistakes, broken
    connections, and unexpected database errors are re-raised.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        result = await db.execute(
            text(
                "SELECT target_id, parse_status, parsed_text "
                "FROM materials "
                "WHERE id = :material_id AND user_id = :user_id "
                "LIMIT 1"
            ),
            {"material_id": material_id, "user_id": user_id},
        )
        row = result.mappings().one_or_none()
    except SQLAlchemyError as exc:
        await db.rollback()
        if _is_missing_materials_table_error(exc):
            return get_mock_material(material_id, user_id=user_id)
        raise

    if row is None:
        return None

    return MaterialSnapshot(
        id=material_id,
        user_id=user_id,
        target_id=int(row["target_id"]) if row["target_id"] is not None else None,
        parse_status=str(row["parse_status"]),
        title="",
        parsed_text=str(row["parsed_text"] or ""),
    )
