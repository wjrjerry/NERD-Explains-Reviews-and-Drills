"""create wrong questions table

Revision ID: b1f6c3d9e2a4
Revises: 9d5f2c8a7e11
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1f6c3d9e2a4'
down_revision: Union[str, Sequence[str], None] = '9d5f2c8a7e11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table for wrong-question book records."""
    bind = op.get_bind()
    mastery_status = postgresql.ENUM(
        'unmastered',
        'reviewing',
        'mastered',
        name='mastery_status',
        create_type=False,
    )
    mastery_status.create(bind, checkfirst=True)

    if inspect(bind).has_table('wrong_questions'):
        return

    op.create_table(
        'wrong_questions',
        sa.Column('id', sa.Integer(), nullable=False, comment='错题记录自增主键ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='错题所属用户ID'),
        sa.Column('test_record_id', sa.Integer(), nullable=False, comment='来源自测记录ID'),
        sa.Column('question_id', sa.Integer(), nullable=False, comment='来源题目ID'),
        sa.Column('target_id', sa.Integer(), nullable=True, comment='课程/考试目标ID，可为空'),
        sa.Column('material_id', sa.Integer(), nullable=False, comment='来源资料ID'),
        sa.Column('stem', sa.Text(), nullable=False, comment='题干快照'),
        sa.Column('user_answer', sa.JSON(), nullable=False, comment='用户错误答案'),
        sa.Column('correct_answer', sa.JSON(), nullable=False, comment='正确答案'),
        sa.Column('analysis', sa.Text(), nullable=False, comment='答案解析'),
        sa.Column('wrong_reason', sa.Text(), nullable=False, comment='错误原因说明'),
        sa.Column('knowledge_points', sa.JSON(), nullable=False, comment='关联知识点'),
        sa.Column('mastery_status', mastery_status, nullable=False, comment='掌握状态'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='错题创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='错题更新时间'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_record_id'], ['test_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_wrong_questions_id'), 'wrong_questions', ['id'], unique=False)
    op.create_index(op.f('ix_wrong_questions_mastery_status'), 'wrong_questions', ['mastery_status'], unique=False)
    op.create_index(op.f('ix_wrong_questions_material_id'), 'wrong_questions', ['material_id'], unique=False)
    op.create_index(op.f('ix_wrong_questions_question_id'), 'wrong_questions', ['question_id'], unique=False)
    op.create_index(op.f('ix_wrong_questions_target_id'), 'wrong_questions', ['target_id'], unique=False)
    op.create_index(op.f('ix_wrong_questions_test_record_id'), 'wrong_questions', ['test_record_id'], unique=False)
    op.create_index(op.f('ix_wrong_questions_user_id'), 'wrong_questions', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop wrong-question book table."""
    bind = op.get_bind()
    if inspect(bind).has_table('wrong_questions'):
        op.drop_index(op.f('ix_wrong_questions_user_id'), table_name='wrong_questions')
        op.drop_index(op.f('ix_wrong_questions_test_record_id'), table_name='wrong_questions')
        op.drop_index(op.f('ix_wrong_questions_target_id'), table_name='wrong_questions')
        op.drop_index(op.f('ix_wrong_questions_question_id'), table_name='wrong_questions')
        op.drop_index(op.f('ix_wrong_questions_material_id'), table_name='wrong_questions')
        op.drop_index(op.f('ix_wrong_questions_mastery_status'), table_name='wrong_questions')
        op.drop_index(op.f('ix_wrong_questions_id'), table_name='wrong_questions')
        op.drop_table('wrong_questions')

    postgresql.ENUM(
        'unmastered',
        'reviewing',
        'mastered',
        name='mastery_status',
        create_type=False,
    ).drop(bind, checkfirst=True)
