"""link qa to targets and knowledge points

Revision ID: a8b9c0d1e2f3
Revises: f7b2c3d4e5a6
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7b2c3d4e5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    """Add target and knowledge-point relations to QA records."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("qa_records") and not _has_column("qa_records", "target_id"):
        op.add_column(
            "qa_records",
            sa.Column(
                "target_id",
                sa.Integer(),
                nullable=True,
                comment="本次问答所属课程/考试目标ID；目标级问答时写入",
            ),
        )
        op.create_foreign_key(
            "fk_qa_records_target_id_study_targets",
            "qa_records",
            "study_targets",
            ["target_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f("ix_qa_records_target_id"), "qa_records", ["target_id"], unique=False)

    if not inspector.has_table("qa_knowledge_points"):
        op.create_table(
            "qa_knowledge_points",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("qa_record_id", sa.Integer(), nullable=False, comment="问答记录ID"),
            sa.Column("knowledge_point_id", sa.Integer(), nullable=False, comment="知识点ID"),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="1.0", comment="问答与知识点的关联强度"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="关联创建时间"),
            sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["qa_record_id"], ["qa_records.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "qa_record_id",
                "knowledge_point_id",
                name="uq_qa_knowledge_points_record_point",
            ),
        )
        op.create_index(op.f("ix_qa_knowledge_points_id"), "qa_knowledge_points", ["id"], unique=False)
        op.create_index(op.f("ix_qa_knowledge_points_knowledge_point_id"), "qa_knowledge_points", ["knowledge_point_id"], unique=False)
        op.create_index(op.f("ix_qa_knowledge_points_qa_record_id"), "qa_knowledge_points", ["qa_record_id"], unique=False)


def downgrade() -> None:
    """Remove QA target and knowledge-point relations."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("qa_knowledge_points"):
        op.drop_index(op.f("ix_qa_knowledge_points_qa_record_id"), table_name="qa_knowledge_points")
        op.drop_index(op.f("ix_qa_knowledge_points_knowledge_point_id"), table_name="qa_knowledge_points")
        op.drop_index(op.f("ix_qa_knowledge_points_id"), table_name="qa_knowledge_points")
        op.drop_table("qa_knowledge_points")

    if inspector.has_table("qa_records") and _has_column("qa_records", "target_id"):
        op.drop_index(op.f("ix_qa_records_target_id"), table_name="qa_records")
        op.drop_constraint("fk_qa_records_target_id_study_targets", "qa_records", type_="foreignkey")
        op.drop_column("qa_records", "target_id")
