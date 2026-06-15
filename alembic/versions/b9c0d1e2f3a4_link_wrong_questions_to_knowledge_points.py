"""link wrong questions to knowledge points

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create wrong-question to knowledge-point relation table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("wrong_question_knowledge_points"):
        return

    op.create_table(
        "wrong_question_knowledge_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wrong_question_id", sa.Integer(), nullable=False, comment="错题记录ID"),
        sa.Column("knowledge_point_id", sa.Integer(), nullable=False, comment="知识点ID"),
        sa.Column("wrong_reason", sa.Text(), nullable=True, comment="该错题在该知识点上的错误原因"),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="1.0", comment="错题与知识点的关联强度"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="关联创建时间"),
        sa.ForeignKeyConstraint(["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wrong_question_id"], ["wrong_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "wrong_question_id",
            "knowledge_point_id",
            name="uq_wrong_question_knowledge_points_wrong_point",
        ),
    )
    op.create_index(op.f("ix_wrong_question_knowledge_points_id"), "wrong_question_knowledge_points", ["id"], unique=False)
    op.create_index(op.f("ix_wrong_question_knowledge_points_knowledge_point_id"), "wrong_question_knowledge_points", ["knowledge_point_id"], unique=False)
    op.create_index(op.f("ix_wrong_question_knowledge_points_wrong_question_id"), "wrong_question_knowledge_points", ["wrong_question_id"], unique=False)


def downgrade() -> None:
    """Drop wrong-question to knowledge-point relation table."""
    bind = op.get_bind()
    if not inspect(bind).has_table("wrong_question_knowledge_points"):
        return

    op.drop_index(op.f("ix_wrong_question_knowledge_points_wrong_question_id"), table_name="wrong_question_knowledge_points")
    op.drop_index(op.f("ix_wrong_question_knowledge_points_knowledge_point_id"), table_name="wrong_question_knowledge_points")
    op.drop_index(op.f("ix_wrong_question_knowledge_points_id"), table_name="wrong_question_knowledge_points")
    op.drop_table("wrong_question_knowledge_points")
