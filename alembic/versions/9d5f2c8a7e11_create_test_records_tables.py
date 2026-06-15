"""create test records tables

Revision ID: 9d5f2c8a7e11
Revises: 8c2f9a1d4b6e
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '9d5f2c8a7e11'
down_revision: Union[str, Sequence[str], None] = '8c2f9a1d4b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tables for self-test summaries and answer details."""
    bind = op.get_bind()

    if not inspect(bind).has_table('test_records'):
        op.create_table(
            'test_records',
            sa.Column('id', sa.Integer(), nullable=False, comment='自测记录自增主键ID'),
            sa.Column('user_id', sa.Integer(), nullable=False, comment='提交自测的用户ID'),
            sa.Column('material_id', sa.Integer(), nullable=False, comment='自测来源资料ID'),
            sa.Column('target_id', sa.Integer(), nullable=True, comment='课程/考试目标ID，可为空'),
            sa.Column('score', sa.Float(), nullable=False, comment='百分制得分'),
            sa.Column('accuracy', sa.Float(), nullable=False, comment='正确率，取值范围 0 到 1'),
            sa.Column('total_count', sa.Integer(), nullable=False, comment='提交题目总数'),
            sa.Column('correct_count', sa.Integer(), nullable=False, comment='答对题目数'),
            sa.Column('wrong_count', sa.Integer(), nullable=False, comment='答错题目数'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='提交时间'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_test_records_id'), 'test_records', ['id'], unique=False)
        op.create_index(op.f('ix_test_records_material_id'), 'test_records', ['material_id'], unique=False)
        op.create_index(op.f('ix_test_records_target_id'), 'test_records', ['target_id'], unique=False)
        op.create_index(op.f('ix_test_records_user_id'), 'test_records', ['user_id'], unique=False)

    if not inspect(bind).has_table('test_answer_records'):
        op.create_table(
            'test_answer_records',
            sa.Column('id', sa.Integer(), nullable=False, comment='作答记录自增主键ID'),
            sa.Column('test_record_id', sa.Integer(), nullable=False, comment='所属自测记录ID'),
            sa.Column('user_id', sa.Integer(), nullable=False, comment='作答用户ID'),
            sa.Column('question_id', sa.Integer(), nullable=False, comment='题目ID'),
            sa.Column('user_answer', sa.JSON(), nullable=False, comment='用户提交答案'),
            sa.Column('correct_answer', sa.JSON(), nullable=False, comment='正确答案'),
            sa.Column('is_correct', sa.Boolean(), nullable=False, comment='是否答对'),
            sa.Column('analysis', sa.Text(), nullable=False, comment='答案解析'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='作答记录创建时间'),
            sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['test_record_id'], ['test_records.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_test_answer_records_id'), 'test_answer_records', ['id'], unique=False)
        op.create_index(op.f('ix_test_answer_records_question_id'), 'test_answer_records', ['question_id'], unique=False)
        op.create_index(op.f('ix_test_answer_records_test_record_id'), 'test_answer_records', ['test_record_id'], unique=False)
        op.create_index(op.f('ix_test_answer_records_user_id'), 'test_answer_records', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop self-test tables."""
    bind = op.get_bind()

    if inspect(bind).has_table('test_answer_records'):
        op.drop_index(op.f('ix_test_answer_records_user_id'), table_name='test_answer_records')
        op.drop_index(op.f('ix_test_answer_records_test_record_id'), table_name='test_answer_records')
        op.drop_index(op.f('ix_test_answer_records_question_id'), table_name='test_answer_records')
        op.drop_index(op.f('ix_test_answer_records_id'), table_name='test_answer_records')
        op.drop_table('test_answer_records')

    if inspect(bind).has_table('test_records'):
        op.drop_index(op.f('ix_test_records_user_id'), table_name='test_records')
        op.drop_index(op.f('ix_test_records_target_id'), table_name='test_records')
        op.drop_index(op.f('ix_test_records_material_id'), table_name='test_records')
        op.drop_index(op.f('ix_test_records_id'), table_name='test_records')
        op.drop_table('test_records')
