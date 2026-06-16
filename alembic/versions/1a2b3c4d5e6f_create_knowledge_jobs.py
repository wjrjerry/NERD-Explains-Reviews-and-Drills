"""create knowledge jobs

Revision ID: 1a2b3c4d5e6f
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("knowledge_jobs"):
        return

    job_type_enum = postgresql.ENUM(
        "material_extract",
        "target_extract",
        "graph_refresh",
        "target_refresh_pipeline",
        name="knowledge_job_type",
        create_type=False,
    )
    status_enum = postgresql.ENUM(
        "pending",
        "running",
        "succeeded",
        "failed",
        name="knowledge_job_status",
        create_type=False,
    )
    postgresql.ENUM(
        "material_extract",
        "target_extract",
        "graph_refresh",
        "target_refresh_pipeline",
        name="knowledge_job_type",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "pending",
        "running",
        "succeeded",
        "failed",
        name="knowledge_job_status",
    ).create(bind, checkfirst=True)

    op.create_table(
        "knowledge_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("job_type", job_type_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("force_regenerate", sa.Boolean(), nullable=False),
        sa.Column("max_points", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=180), nullable=False),
        sa.Column("rerun_requested", sa.Boolean(), nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["study_targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_knowledge_jobs_dedupe_key"),
    )
    op.create_index(op.f("ix_knowledge_jobs_id"), "knowledge_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_knowledge_jobs_user_id"), "knowledge_jobs", ["user_id"], unique=False)
    op.create_index(op.f("ix_knowledge_jobs_target_id"), "knowledge_jobs", ["target_id"], unique=False)
    op.create_index(op.f("ix_knowledge_jobs_material_id"), "knowledge_jobs", ["material_id"], unique=False)
    op.create_index(op.f("ix_knowledge_jobs_job_type"), "knowledge_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_knowledge_jobs_status"), "knowledge_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_knowledge_jobs_dedupe_key"), "knowledge_jobs", ["dedupe_key"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("knowledge_jobs"):
        op.drop_index(op.f("ix_knowledge_jobs_dedupe_key"), table_name="knowledge_jobs")
        op.drop_index(op.f("ix_knowledge_jobs_status"), table_name="knowledge_jobs")
        op.drop_index(op.f("ix_knowledge_jobs_job_type"), table_name="knowledge_jobs")
        op.drop_index(op.f("ix_knowledge_jobs_material_id"), table_name="knowledge_jobs")
        op.drop_index(op.f("ix_knowledge_jobs_target_id"), table_name="knowledge_jobs")
        op.drop_index(op.f("ix_knowledge_jobs_user_id"), table_name="knowledge_jobs")
        op.drop_index(op.f("ix_knowledge_jobs_id"), table_name="knowledge_jobs")
        op.drop_table("knowledge_jobs")
    sa.Enum(name="knowledge_job_status").drop(bind, checkfirst=True)
    sa.Enum(name="knowledge_job_type").drop(bind, checkfirst=True)
