"""create knowledge extractions

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table for material-level and target-level knowledge extraction."""
    bind = op.get_bind()
    inspector = inspect(bind)

    scope_enum = postgresql.ENUM(
        "material",
        "target",
        name="knowledge_extraction_scope",
        create_type=False,
    )
    status_enum = postgresql.ENUM(
        "completed",
        "failed",
        name="knowledge_extraction_status",
        create_type=False,
    )
    scope_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)

    if inspector.has_table("knowledge_extractions"):
        return

    op.create_table(
        "knowledge_extractions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="提炼结果所属用户ID"),
        sa.Column("target_id", sa.Integer(), nullable=True, comment="目标级提炼所属课程/考试目标ID"),
        sa.Column("material_id", sa.Integer(), nullable=True, comment="资料级提炼所属资料ID"),
        sa.Column("scope", scope_enum, nullable=False, comment="提炼范围：material 或 target"),
        sa.Column("status", status_enum, nullable=False, comment="提炼状态"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("outline", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("key_points", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("exam_points", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["study_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_extractions_id"), "knowledge_extractions", ["id"], unique=False)
    op.create_index(op.f("ix_knowledge_extractions_material_id"), "knowledge_extractions", ["material_id"], unique=False)
    op.create_index(op.f("ix_knowledge_extractions_scope"), "knowledge_extractions", ["scope"], unique=False)
    op.create_index(op.f("ix_knowledge_extractions_status"), "knowledge_extractions", ["status"], unique=False)
    op.create_index(op.f("ix_knowledge_extractions_target_id"), "knowledge_extractions", ["target_id"], unique=False)
    op.create_index(op.f("ix_knowledge_extractions_user_id"), "knowledge_extractions", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop knowledge extractions table."""
    bind = op.get_bind()
    if inspect(bind).has_table("knowledge_extractions"):
        op.drop_index(op.f("ix_knowledge_extractions_user_id"), table_name="knowledge_extractions")
        op.drop_index(op.f("ix_knowledge_extractions_target_id"), table_name="knowledge_extractions")
        op.drop_index(op.f("ix_knowledge_extractions_status"), table_name="knowledge_extractions")
        op.drop_index(op.f("ix_knowledge_extractions_scope"), table_name="knowledge_extractions")
        op.drop_index(op.f("ix_knowledge_extractions_material_id"), table_name="knowledge_extractions")
        op.drop_index(op.f("ix_knowledge_extractions_id"), table_name="knowledge_extractions")
        op.drop_table("knowledge_extractions")

    postgresql.ENUM(
        "completed",
        "failed",
        name="knowledge_extraction_status",
        create_type=False,
    ).drop(bind, checkfirst=True)
    postgresql.ENUM(
        "material",
        "target",
        name="knowledge_extraction_scope",
        create_type=False,
    ).drop(bind, checkfirst=True)
