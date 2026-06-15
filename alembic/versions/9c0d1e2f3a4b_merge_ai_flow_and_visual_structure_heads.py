"""merge ai flow and visual structure heads

Revision ID: 9c0d1e2f3a4b
Revises: 8b7d3c2a1f90, f0a1b2c3d4e5
Create Date: 2026-06-15 20:50:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "9c0d1e2f3a4b"
down_revision: Union[str, Sequence[str], None] = (
    "8b7d3c2a1f90",
    "f0a1b2c3d4e5",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration branches without schema changes."""


def downgrade() -> None:
    """No schema changes to revert."""
