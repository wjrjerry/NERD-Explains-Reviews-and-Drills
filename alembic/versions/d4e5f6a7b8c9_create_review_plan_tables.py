"""create review plan tables

Revision ID: d4e5f6a7b8c9
Revises: c7a8e9f1b2d3
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c7a8e9f1b2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create review plan and task tables."""
    bind = op.get_bind()

    if not inspect(bind).has_table('review_plans'):
        op.create_table(
            'review_plans',
            sa.Column('id', sa.Integer(), nullable=False, comment='复习计划自增主键ID'),
            sa.Column('user_id', sa.Integer(), nullable=False, comment='计划所属用户ID'),
            sa.Column('target_id', sa.Integer(), nullable=False, comment='课程/考试目标ID'),
            sa.Column('title', sa.String(length=120), nullable=False, comment='复习计划标题'),
            sa.Column('start_date', sa.Date(), nullable=False, comment='计划开始日期'),
            sa.Column('end_date', sa.Date(), nullable=False, comment='计划结束日期'),
            sa.Column('summary', sa.Text(), nullable=False, comment='计划生成依据摘要'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='计划创建时间'),
            sa.ForeignKeyConstraint(['target_id'], ['study_targets.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_review_plans_id'), 'review_plans', ['id'], unique=False)
        op.create_index(op.f('ix_review_plans_target_id'), 'review_plans', ['target_id'], unique=False)
        op.create_index(op.f('ix_review_plans_user_id'), 'review_plans', ['user_id'], unique=False)

    if not inspect(bind).has_table('review_plan_tasks'):
        op.create_table(
            'review_plan_tasks',
            sa.Column('id', sa.Integer(), nullable=False, comment='复习任务自增主键ID'),
            sa.Column('plan_id', sa.Integer(), nullable=False, comment='所属复习计划ID'),
            sa.Column('task_date', sa.Date(), nullable=False, comment='任务日期'),
            sa.Column('title', sa.String(length=160), nullable=False, comment='任务标题'),
            sa.Column('content', sa.Text(), nullable=False, comment='任务内容'),
            sa.Column('material_id', sa.Integer(), nullable=True, comment='关联资料ID，可为空'),
            sa.Column('wrong_question_id', sa.Integer(), nullable=True, comment='关联错题ID，可为空'),
            sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='任务是否完成'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='任务创建时间'),
            sa.ForeignKeyConstraint(['plan_id'], ['review_plans.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['wrong_question_id'], ['wrong_questions.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_review_plan_tasks_id'), 'review_plan_tasks', ['id'], unique=False)
        op.create_index(op.f('ix_review_plan_tasks_material_id'), 'review_plan_tasks', ['material_id'], unique=False)
        op.create_index(op.f('ix_review_plan_tasks_plan_id'), 'review_plan_tasks', ['plan_id'], unique=False)
        op.create_index(op.f('ix_review_plan_tasks_task_date'), 'review_plan_tasks', ['task_date'], unique=False)
        op.create_index(op.f('ix_review_plan_tasks_wrong_question_id'), 'review_plan_tasks', ['wrong_question_id'], unique=False)
        op.alter_column('review_plan_tasks', 'completed', server_default=None)


def downgrade() -> None:
    """Drop review plan and task tables."""
    bind = op.get_bind()

    if inspect(bind).has_table('review_plan_tasks'):
        op.drop_index(op.f('ix_review_plan_tasks_wrong_question_id'), table_name='review_plan_tasks')
        op.drop_index(op.f('ix_review_plan_tasks_task_date'), table_name='review_plan_tasks')
        op.drop_index(op.f('ix_review_plan_tasks_plan_id'), table_name='review_plan_tasks')
        op.drop_index(op.f('ix_review_plan_tasks_material_id'), table_name='review_plan_tasks')
        op.drop_index(op.f('ix_review_plan_tasks_id'), table_name='review_plan_tasks')
        op.drop_table('review_plan_tasks')

    if inspect(bind).has_table('review_plans'):
        op.drop_index(op.f('ix_review_plans_user_id'), table_name='review_plans')
        op.drop_index(op.f('ix_review_plans_target_id'), table_name='review_plans')
        op.drop_index(op.f('ix_review_plans_id'), table_name='review_plans')
        op.drop_table('review_plans')
