"""create questions table

Revision ID: 8c2f9a1d4b6e
Revises: 2b7c5f1a9d30
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8c2f9a1d4b6e'
down_revision: Union[str, Sequence[str], None] = '2b7c5f1a9d30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table for persisted AI-generated questions."""
    bind = op.get_bind()
    question_type = postgresql.ENUM(
        'single_choice',
        'multiple_choice',
        'true_false',
        name='question_type',
        create_type=False,
    )
    question_difficulty = postgresql.ENUM(
        'easy',
        'medium',
        'hard',
        name='question_difficulty',
        create_type=False,
    )
    question_type.create(bind, checkfirst=True)
    question_difficulty.create(bind, checkfirst=True)

    if inspect(bind).has_table('questions'):
        return

    op.create_table(
        'questions',
        sa.Column('id', sa.Integer(), nullable=False, comment='题目自增主键ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='题目所属用户ID'),
        sa.Column('material_id', sa.Integer(), nullable=False, comment='题目来源资料ID，后续可与 materials 表建立外键'),
        sa.Column('question_type', question_type, nullable=False, comment='题型：单选、多选或判断'),
        sa.Column('stem', sa.Text(), nullable=False, comment='题干'),
        sa.Column('options', sa.JSON(), nullable=False, comment="选项列表，例如 [{'key': 'A', 'text': '...'}]"),
        sa.Column('correct_answer', sa.JSON(), nullable=False, comment='正确答案列表'),
        sa.Column('analysis', sa.Text(), nullable=False, comment='答案解析'),
        sa.Column('knowledge_points', sa.JSON(), nullable=False, comment='题目关联知识点'),
        sa.Column('difficulty', question_difficulty, nullable=False, comment='题目难度'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='题目创建时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_questions_difficulty'), 'questions', ['difficulty'], unique=False)
    op.create_index(op.f('ix_questions_id'), 'questions', ['id'], unique=False)
    op.create_index(op.f('ix_questions_material_id'), 'questions', ['material_id'], unique=False)
    op.create_index(op.f('ix_questions_question_type'), 'questions', ['question_type'], unique=False)
    op.create_index(op.f('ix_questions_user_id'), 'questions', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop table for persisted AI-generated questions."""
    bind = op.get_bind()
    if inspect(bind).has_table('questions'):
        op.drop_index(op.f('ix_questions_user_id'), table_name='questions')
        op.drop_index(op.f('ix_questions_question_type'), table_name='questions')
        op.drop_index(op.f('ix_questions_material_id'), table_name='questions')
        op.drop_index(op.f('ix_questions_id'), table_name='questions')
        op.drop_index(op.f('ix_questions_difficulty'), table_name='questions')
        op.drop_table('questions')

    postgresql.ENUM(
        'easy',
        'medium',
        'hard',
        name='question_difficulty',
        create_type=False,
    ).drop(bind, checkfirst=True)
    postgresql.ENUM(
        'single_choice',
        'multiple_choice',
        'true_false',
        name='question_type',
        create_type=False,
    ).drop(bind, checkfirst=True)
