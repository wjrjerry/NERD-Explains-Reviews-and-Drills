"""create qa records table

Revision ID: 2b7c5f1a9d30
Revises: 14f6398ed468
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '2b7c5f1a9d30'
down_revision: Union[str, Sequence[str], None] = '14de6dec0d7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create table for persisted material-based QA records."""
    bind = op.get_bind()
    if inspect(bind).has_table('qa_records'):
        return

    op.create_table(
        'qa_records',
        sa.Column('id', sa.Integer(), nullable=False, comment='问答记录自增主键ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='发起提问的用户ID'),
        sa.Column('material_id', sa.Integer(), nullable=False, comment='本次问答所依据的资料ID，后续可与 materials 表建立外键'),
        sa.Column('question', sa.Text(), nullable=False, comment='用户提交的原始问题'),
        sa.Column('answer', sa.Text(), nullable=False, comment='AI 根据资料生成的回答'),
        sa.Column('references', sa.JSON(), nullable=False, comment='回答引用的资料片段列表'),
        sa.Column('ai_provider', sa.String(length=50), nullable=False, comment='生成回答时使用的 AI 提供方，例如 mock 或 openai-compatible'),
        sa.Column('ai_model', sa.String(length=100), nullable=True, comment='生成回答时使用的模型名，mock 模式下可为空'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='问答记录创建时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_qa_records_id'), 'qa_records', ['id'], unique=False)
    op.create_index(op.f('ix_qa_records_material_id'), 'qa_records', ['material_id'], unique=False)
    op.create_index(op.f('ix_qa_records_user_id'), 'qa_records', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop table for persisted material-based QA records."""
    bind = op.get_bind()
    if not inspect(bind).has_table('qa_records'):
        return

    op.drop_index(op.f('ix_qa_records_user_id'), table_name='qa_records')
    op.drop_index(op.f('ix_qa_records_material_id'), table_name='qa_records')
    op.drop_index(op.f('ix_qa_records_id'), table_name='qa_records')
    op.drop_table('qa_records')
