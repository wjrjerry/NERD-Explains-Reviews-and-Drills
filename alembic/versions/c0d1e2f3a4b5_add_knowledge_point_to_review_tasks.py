"""add knowledge point to review tasks

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    """Add optional knowledge point relation to review plan tasks."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("review_plan_tasks"):
        return
    if _has_column("review_plan_tasks", "knowledge_point_id"):
        return

    op.add_column(
        "review_plan_tasks",
        sa.Column(
            "knowledge_point_id",
            sa.Integer(),
            nullable=True,
            comment="关联知识点ID，可为空",
        ),
    )
    op.create_foreign_key(
        "fk_review_plan_tasks_knowledge_point_id",
        "review_plan_tasks",
        "knowledge_points",
        ["knowledge_point_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_review_plan_tasks_knowledge_point_id"),
        "review_plan_tasks",
        ["knowledge_point_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove optional knowledge point relation from review plan tasks."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("review_plan_tasks"):
        return
    if not _has_column("review_plan_tasks", "knowledge_point_id"):
        return

    op.drop_index(op.f("ix_review_plan_tasks_knowledge_point_id"), table_name="review_plan_tasks")
    op.drop_constraint(
        "fk_review_plan_tasks_knowledge_point_id",
        "review_plan_tasks",
        type_="foreignkey",
    )
    op.drop_column("review_plan_tasks", "knowledge_point_id")
