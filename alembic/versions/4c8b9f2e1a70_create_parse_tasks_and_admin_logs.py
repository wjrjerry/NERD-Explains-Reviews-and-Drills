"""create parse tasks and admin logs

Revision ID: 4c8b9f2e1a70
Revises: 14de6dec0d7c
Create Date: 2026-06-12 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4c8b9f2e1a70"
down_revision: Union[str, Sequence[str], None] = "14de6dec0d7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create parse task and admin log tables."""
    bind = op.get_bind()
    inspector = inspect(bind)

    parse_task_type = postgresql.ENUM(
        "material_parse",
        name="parse_task_type",
        create_type=False,
    )
    parse_task_status = postgresql.ENUM(
        "pending",
        "running",
        "succeeded",
        "failed",
        name="parse_task_status",
        create_type=False,
    )
    parse_task_type.create(bind, checkfirst=True)
    parse_task_status.create(bind, checkfirst=True)

    if not inspector.has_table("parse_tasks"):
        op.create_table(
            "parse_tasks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False, comment="关联资料 ID"),
            sa.Column("user_id", sa.Integer(), nullable=False, comment="资料所属用户 ID"),
            sa.Column("task_type", parse_task_type, nullable=False, comment="任务类型"),
            sa.Column("task_status", parse_task_status, nullable=False, comment="任务状态"),
            sa.Column("retry_count", sa.Integer(), nullable=False, comment="重试次数"),
            sa.Column("failure_reason", sa.Text(), nullable=True, comment="失败原因"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="开始执行时间"),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, comment="执行结束时间"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
                comment="创建时间",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
                comment="更新时间",
            ),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_parse_tasks_id"), "parse_tasks", ["id"], unique=False)
        op.create_index(op.f("ix_parse_tasks_material_id"), "parse_tasks", ["material_id"], unique=False)
        op.create_index(op.f("ix_parse_tasks_task_status"), "parse_tasks", ["task_status"], unique=False)
        op.create_index(op.f("ix_parse_tasks_user_id"), "parse_tasks", ["user_id"], unique=False)

    if not inspector.has_table("admin_logs"):
        op.create_table(
            "admin_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("admin_user_id", sa.Integer(), nullable=False, comment="执行操作的管理员用户 ID"),
            sa.Column("operation_type", sa.String(length=50), nullable=False, comment="操作类型"),
            sa.Column("target_type", sa.String(length=50), nullable=False, comment="操作对象类型"),
            sa.Column("target_id", sa.Integer(), nullable=True, comment="操作对象 ID"),
            sa.Column("operation_result", sa.String(length=20), nullable=False, comment="操作结果"),
            sa.Column("remark", sa.Text(), nullable=True, comment="备注信息"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
                comment="日志创建时间",
            ),
            sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_admin_logs_admin_user_id"), "admin_logs", ["admin_user_id"], unique=False)
        op.create_index(op.f("ix_admin_logs_id"), "admin_logs", ["id"], unique=False)
        op.create_index(op.f("ix_admin_logs_operation_result"), "admin_logs", ["operation_result"], unique=False)
        op.create_index(op.f("ix_admin_logs_operation_type"), "admin_logs", ["operation_type"], unique=False)
        op.create_index(op.f("ix_admin_logs_target_id"), "admin_logs", ["target_id"], unique=False)
        op.create_index(op.f("ix_admin_logs_target_type"), "admin_logs", ["target_type"], unique=False)


def downgrade() -> None:
    """Drop parse task and admin log tables."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("admin_logs"):
        op.drop_index(op.f("ix_admin_logs_target_type"), table_name="admin_logs")
        op.drop_index(op.f("ix_admin_logs_target_id"), table_name="admin_logs")
        op.drop_index(op.f("ix_admin_logs_operation_type"), table_name="admin_logs")
        op.drop_index(op.f("ix_admin_logs_operation_result"), table_name="admin_logs")
        op.drop_index(op.f("ix_admin_logs_id"), table_name="admin_logs")
        op.drop_index(op.f("ix_admin_logs_admin_user_id"), table_name="admin_logs")
        op.drop_table("admin_logs")

    if inspector.has_table("parse_tasks"):
        op.drop_index(op.f("ix_parse_tasks_user_id"), table_name="parse_tasks")
        op.drop_index(op.f("ix_parse_tasks_task_status"), table_name="parse_tasks")
        op.drop_index(op.f("ix_parse_tasks_material_id"), table_name="parse_tasks")
        op.drop_index(op.f("ix_parse_tasks_id"), table_name="parse_tasks")
        op.drop_table("parse_tasks")

    postgresql.ENUM("pending", "running", "succeeded", "failed", name="parse_task_status").drop(
        bind,
        checkfirst=True,
    )
    postgresql.ENUM("material_parse", name="parse_task_type").drop(bind, checkfirst=True)
