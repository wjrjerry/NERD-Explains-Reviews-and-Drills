"""link questions to knowledge points

Revision ID: f7b2c3d4e5a6
Revises: e6a1b2c3d4f5
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "f7b2c3d4e5a6"
down_revision: Union[str, Sequence[str], None] = "e6a1b2c3d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    """Add target-level ownership and question-knowledge-point relation table."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("questions") and not _has_column("questions", "target_id"):
        op.add_column(
            "questions",
            sa.Column(
                "target_id",
                sa.Integer(),
                nullable=True,
                comment="题目所属课程/考试目标ID；知识图谱出题时用于目标级归属",
            ),
        )
        op.create_foreign_key(
            "fk_questions_target_id_study_targets",
            "questions",
            "study_targets",
            ["target_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f("ix_questions_target_id"), "questions", ["target_id"], unique=False)

    if not inspector.has_table("question_knowledge_points"):
        op.create_table(
            "question_knowledge_points",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("question_id", sa.Integer(), nullable=False, comment="题目ID"),
            sa.Column("knowledge_point_id", sa.Integer(), nullable=False, comment="知识点ID"),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="1.0", comment="题目与知识点的关联强度"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="关联创建时间"),
            sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "question_id",
                "knowledge_point_id",
                name="uq_question_knowledge_points_question_point",
            ),
        )
        op.create_index(op.f("ix_question_knowledge_points_id"), "question_knowledge_points", ["id"], unique=False)
        op.create_index(op.f("ix_question_knowledge_points_knowledge_point_id"), "question_knowledge_points", ["knowledge_point_id"], unique=False)
        op.create_index(op.f("ix_question_knowledge_points_question_id"), "question_knowledge_points", ["question_id"], unique=False)


def downgrade() -> None:
    """Remove question-knowledge-point relation table."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("question_knowledge_points"):
        op.drop_index(op.f("ix_question_knowledge_points_question_id"), table_name="question_knowledge_points")
        op.drop_index(op.f("ix_question_knowledge_points_knowledge_point_id"), table_name="question_knowledge_points")
        op.drop_index(op.f("ix_question_knowledge_points_id"), table_name="question_knowledge_points")
        op.drop_table("question_knowledge_points")

    if inspector.has_table("questions") and _has_column("questions", "target_id"):
        op.drop_index(op.f("ix_questions_target_id"), table_name="questions")
        op.drop_constraint("fk_questions_target_id_study_targets", "questions", type_="foreignkey")
        op.drop_column("questions", "target_id")
