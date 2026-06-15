"""create material structure tables

Revision ID: 6f2a9c1d8e34
Revises: 4c8b9f2e1a70
Create Date: 2026-06-15 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "6f2a9c1d8e34"
down_revision: Union[str, Sequence[str], None] = "4c8b9f2e1a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create material sections and chunks."""
    bind = op.get_bind()
    inspector = inspect(bind)

    chunk_type = postgresql.ENUM(
        "text",
        "definition",
        "formula",
        "example",
        "key_sentence",
        name="material_chunk_type",
        create_type=False,
    )
    chunk_type.create(bind, checkfirst=True)

    if not inspector.has_table("material_sections"):
        op.create_table(
            "material_sections",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False, comment="关联资料 ID"),
            sa.Column("parent_id", sa.Integer(), nullable=True, comment="父章节 ID"),
            sa.Column("title", sa.String(length=255), nullable=False, comment="章节标题"),
            sa.Column("level", sa.Integer(), nullable=False, comment="章节层级"),
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
            sa.ForeignKeyConstraint(["parent_id"], ["material_sections.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_material_sections_id"), "material_sections", ["id"], unique=False)
        op.create_index(
            op.f("ix_material_sections_material_id"),
            "material_sections",
            ["material_id"],
            unique=False,
        )
        op.create_index(op.f("ix_material_sections_parent_id"), "material_sections", ["parent_id"], unique=False)

    if not inspector.has_table("material_chunks"):
        op.create_table(
            "material_chunks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False, comment="关联资料 ID"),
            sa.Column("section_id", sa.Integer(), nullable=True, comment="关联章节 ID"),
            sa.Column("chunk_type", chunk_type, nullable=False, comment="文本块类型"),
            sa.Column("title", sa.String(length=255), nullable=True, comment="文本块标题"),
            sa.Column("text", sa.Text(), nullable=False, comment="文本块内容"),
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
        op.create_index(op.f("ix_material_chunks_chunk_type"), "material_chunks", ["chunk_type"], unique=False)
        op.create_index(op.f("ix_material_chunks_id"), "material_chunks", ["id"], unique=False)
        op.create_index(op.f("ix_material_chunks_material_id"), "material_chunks", ["material_id"], unique=False)
        op.create_index(op.f("ix_material_chunks_section_id"), "material_chunks", ["section_id"], unique=False)


def downgrade() -> None:
    """Drop material sections and chunks."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("material_chunks"):
        op.drop_index(op.f("ix_material_chunks_section_id"), table_name="material_chunks")
        op.drop_index(op.f("ix_material_chunks_material_id"), table_name="material_chunks")
        op.drop_index(op.f("ix_material_chunks_id"), table_name="material_chunks")
        op.drop_index(op.f("ix_material_chunks_chunk_type"), table_name="material_chunks")
        op.drop_table("material_chunks")

    if inspector.has_table("material_sections"):
        op.drop_index(op.f("ix_material_sections_parent_id"), table_name="material_sections")
        op.drop_index(op.f("ix_material_sections_material_id"), table_name="material_sections")
        op.drop_index(op.f("ix_material_sections_id"), table_name="material_sections")
        op.drop_table("material_sections")

    postgresql.ENUM(
        "text",
        "definition",
        "formula",
        "example",
        "key_sentence",
        name="material_chunk_type",
    ).drop(bind, checkfirst=True)
