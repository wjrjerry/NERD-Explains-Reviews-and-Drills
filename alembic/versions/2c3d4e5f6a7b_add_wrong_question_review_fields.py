"""add wrong question review fields

Revision ID: 2c3d4e5f6a7b
Revises: 1a2b3c4d5e6f
Create Date: 2026-06-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "2c3d4e5f6a7b"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("wrong_questions")
    if not columns:
        return

    if "review_count" not in columns:
        op.add_column(
            "wrong_questions",
            sa.Column(
                "review_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
                comment="错题复习次数",
            ),
        )
    if "last_reviewed_at" not in columns:
        op.add_column(
            "wrong_questions",
            sa.Column(
                "last_reviewed_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="最近一次复习时间",
            ),
        )
    if "next_review_at" not in columns:
        op.add_column(
            "wrong_questions",
            sa.Column(
                "next_review_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="建议下次复习时间",
            ),
        )
        op.create_index(
            op.f("ix_wrong_questions_next_review_at"),
            "wrong_questions",
            ["next_review_at"],
            unique=False,
        )


def downgrade() -> None:
    columns = _column_names("wrong_questions")
    if "next_review_at" in columns:
        op.drop_index(op.f("ix_wrong_questions_next_review_at"), table_name="wrong_questions")
        op.drop_column("wrong_questions", "next_review_at")
    if "last_reviewed_at" in columns:
        op.drop_column("wrong_questions", "last_reviewed_at")
    if "review_count" in columns:
        op.drop_column("wrong_questions", "review_count")
