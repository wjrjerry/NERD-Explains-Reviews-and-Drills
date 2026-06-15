"""add subjective question support

Revision ID: c7a8e9f1b2d3
Revises: b1f6c3d9e2a4
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c7a8e9f1b2d3'
down_revision: Union[str, Sequence[str], None] = 'b1f6c3d9e2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow subjective questions and persist per-question score."""
    bind = op.get_bind()
    op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'subjective'")

    columns = {
        column['name']
        for column in inspect(bind).get_columns('test_answer_records')
    }
    if 'score' not in columns:
        op.add_column(
            'test_answer_records',
            sa.Column(
                'score',
                sa.Float(),
                nullable=False,
                server_default='0',
                comment='单题得分，取值范围 0 到 1',
            ),
        )
        op.alter_column('test_answer_records', 'score', server_default=None)


def downgrade() -> None:
    """Remove per-question score column.

    PostgreSQL enum values cannot be removed safely without recreating the type,
    so the subjective enum value is intentionally kept on downgrade.
    """
    bind = op.get_bind()
    columns = {
        column['name']
        for column in inspect(bind).get_columns('test_answer_records')
    }
    if 'score' in columns:
        op.drop_column('test_answer_records', 'score')
