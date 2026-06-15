"""create ai call logs

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-15 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ai_call_status = postgresql.ENUM(
    "success",
    "failed",
    name="ai_call_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    ai_call_status.create(bind, checkfirst=True)

    op.create_table(
        "ai_call_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="发起本次 AI 调用的用户ID"),
        sa.Column("target_id", sa.Integer(), nullable=True, comment="调用关联的课程/考试目标ID"),
        sa.Column("material_id", sa.Integer(), nullable=True, comment="调用关联的资料ID"),
        sa.Column("feature", sa.String(length=80), nullable=False, comment="业务功能，例如 qa、question_generation、knowledge_graph_generation"),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("status", ai_call_status, nullable=False),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_cache_hit_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_cache_miss_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=False, comment="按本平台本地 token 单价估算的费用"),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("billing_policy_version", sa.String(length=50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_chars", sa.Integer(), nullable=False),
        sa.Column("completion_chars", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["target_id"], ["study_targets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_call_logs_created_at"), "ai_call_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_ai_call_logs_feature"), "ai_call_logs", ["feature"], unique=False)
    op.create_index(op.f("ix_ai_call_logs_id"), "ai_call_logs", ["id"], unique=False)
    op.create_index(op.f("ix_ai_call_logs_material_id"), "ai_call_logs", ["material_id"], unique=False)
    op.create_index(op.f("ix_ai_call_logs_status"), "ai_call_logs", ["status"], unique=False)
    op.create_index(op.f("ix_ai_call_logs_target_id"), "ai_call_logs", ["target_id"], unique=False)
    op.create_index(op.f("ix_ai_call_logs_user_id"), "ai_call_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_call_logs_user_id"), table_name="ai_call_logs")
    op.drop_index(op.f("ix_ai_call_logs_target_id"), table_name="ai_call_logs")
    op.drop_index(op.f("ix_ai_call_logs_status"), table_name="ai_call_logs")
    op.drop_index(op.f("ix_ai_call_logs_material_id"), table_name="ai_call_logs")
    op.drop_index(op.f("ix_ai_call_logs_id"), table_name="ai_call_logs")
    op.drop_index(op.f("ix_ai_call_logs_feature"), table_name="ai_call_logs")
    op.drop_index(op.f("ix_ai_call_logs_created_at"), table_name="ai_call_logs")
    op.drop_table("ai_call_logs")
    ai_call_status.drop(op.get_bind(), checkfirst=True)
