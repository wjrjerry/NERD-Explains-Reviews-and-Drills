"""add material visual structure tables

Revision ID: 8b7d3c2a1f90
Revises: 7c3b9e1a5d20
Create Date: 2026-06-15 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "8b7d3c2a1f90"
down_revision: Union[str, Sequence[str], None] = "7c3b9e1a5d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_common_indexes(table_name: str) -> None:
    op.create_index(op.f(f"ix_{table_name}_id"), table_name, ["id"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_material_id"), table_name, ["material_id"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_section_id"), table_name, ["section_id"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("material_figures"):
        op.create_table(
            "material_figures",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False, comment="关联资料 ID"),
            sa.Column("section_id", sa.Integer(), nullable=True, comment="关联章节 ID"),
            sa.Column("title", sa.String(length=255), nullable=True, comment="图片标题"),
            sa.Column("description", sa.Text(), nullable=False, comment="图片或图形说明"),
            sa.Column("order_index", sa.Integer(), nullable=False, comment="排序序号"),
            sa.Column("source_page", sa.Integer(), nullable=True, comment="来源页码"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["section_id"], ["material_sections.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_common_indexes("material_figures")

    if not inspector.has_table("material_tables"):
        op.create_table(
            "material_tables",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False, comment="关联资料 ID"),
            sa.Column("section_id", sa.Integer(), nullable=True, comment="关联章节 ID"),
            sa.Column("title", sa.String(length=255), nullable=True, comment="表格标题"),
            sa.Column("content", sa.Text(), nullable=False, comment="Markdown 或纯文本表格内容"),
            sa.Column("order_index", sa.Integer(), nullable=False, comment="排序序号"),
            sa.Column("source_page", sa.Integer(), nullable=True, comment="来源页码"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["section_id"], ["material_sections.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_common_indexes("material_tables")

    if not inspector.has_table("material_formulas"):
        op.create_table(
            "material_formulas",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False, comment="关联资料 ID"),
            sa.Column("section_id", sa.Integer(), nullable=True, comment="关联章节 ID"),
            sa.Column("expression", sa.Text(), nullable=False, comment="公式表达式或 LaTeX"),
            sa.Column("explanation", sa.Text(), nullable=True, comment="公式解释"),
            sa.Column("order_index", sa.Integer(), nullable=False, comment="排序序号"),
            sa.Column("source_page", sa.Integer(), nullable=True, comment="来源页码"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["section_id"], ["material_sections.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        _create_common_indexes("material_formulas")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for table_name in ("material_formulas", "material_tables", "material_figures"):
        if inspector.has_table(table_name):
            op.drop_index(op.f(f"ix_{table_name}_section_id"), table_name=table_name)
            op.drop_index(op.f(f"ix_{table_name}_material_id"), table_name=table_name)
            op.drop_index(op.f(f"ix_{table_name}_id"), table_name=table_name)
            op.drop_table(table_name)
