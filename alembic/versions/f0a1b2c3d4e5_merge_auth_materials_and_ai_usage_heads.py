"""merge auth materials and ai usage heads

Revision ID: f0a1b2c3d4e5
Revises: 7c3b9e1a5d20, e2f3a4b5c6d7
Create Date: 2026-06-15 00:00:00.000000
"""

from typing import Sequence, Union


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = (
    "7c3b9e1a5d20",
    "e2f3a4b5c6d7",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration branches without schema changes."""


def downgrade() -> None:
    """No schema changes to revert."""
