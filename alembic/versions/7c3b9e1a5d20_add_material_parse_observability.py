"""add material parse observability

Revision ID: 7c3b9e1a5d20
Revises: 6f2a9c1d8e34
Create Date: 2026-06-15 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "7c3b9e1a5d20"
down_revision: Union[str, Sequence[str], None] = "6f2a9c1d8e34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parse warning and metadata fields to materials."""
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("materials")}

    if "parse_warning" not in columns:
        op.add_column(
            "materials",
            sa.Column("parse_warning", sa.Text(), nullable=True, comment="资料解析质量提示或风险说明"),
        )

    if "parse_metadata" not in columns:
        op.add_column(
            "materials",
            sa.Column(
                "parse_metadata",
                sa.Text(),
                nullable=True,
                comment="资料解析过程元数据 JSON，例如页数、耗时、失败页码等",
            ),
        )


def downgrade() -> None:
    """Remove parse warning and metadata fields from materials."""
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("materials")}

    if "parse_metadata" in columns:
        op.drop_column("materials", "parse_metadata")

    if "parse_warning" in columns:
        op.drop_column("materials", "parse_warning")
