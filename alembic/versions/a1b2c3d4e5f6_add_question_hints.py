"""add progressive hints to questions

Revision ID: a1b2c3d4e5f6
Revises: 9c0d1e2f3a4b
Create Date: 2026-06-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9c0d1e2f3a4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name)
    )


def upgrade() -> None:
    """Persist three progressively stronger learning hints per question."""
    if inspect(op.get_bind()).has_table("questions") and not _has_column(
        "questions",
        "hints",
    ):
        op.add_column(
            "questions",
            sa.Column(
                "hints",
                sa.JSON(),
                server_default=sa.text("'[]'::json"),
                nullable=False,
                comment="逐层学习提示，按由浅入深顺序保存",
            ),
        )


def downgrade() -> None:
    """Remove persisted question hints."""
    if inspect(op.get_bind()).has_table("questions") and _has_column(
        "questions",
        "hints",
    ):
        op.drop_column("questions", "hints")
