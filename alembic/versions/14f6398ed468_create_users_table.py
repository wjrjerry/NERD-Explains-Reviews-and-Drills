"""create users table

Revision ID: 14f6398ed468
Revises: 
Create Date: 2026-05-25 19:58:16.988930

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '14f6398ed468'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    user_role = postgresql.ENUM(
        'student',
        'admin',
        name='user_role',
        create_type=False,
    )
    user_role.create(bind, checkfirst=True)

    # During early development, some local databases may already have the users
    # table because the app previously used Base.metadata.create_all(). Keep this
    # migration tolerant so those databases can be stamped by Alembic cleanly.
    if inspect(bind).has_table('users'):
        return

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False, comment='自增主键ID'),
    sa.Column('username', sa.String(length=50), nullable=False, comment='唯一个体用户名'),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=50), nullable=True, comment='用户昵称，可空'),
    sa.Column('role', user_role, nullable=False, comment='系统权限角色，默认指定为student'),
    sa.Column('is_active', sa.Boolean(), nullable=False, comment='账户激活状态，False表示账户被封'),
    sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='更新该字段为True即视作删除'),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='最后完成鉴权登录的带时区时间戳'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='记录创建时间，由持久层数据库内核生成'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='记录最终修改时间，每当该用户的任意其他字段被更新并触发 UPDATE 语句提交时，SQLAlchemy 引擎会自动将该值强行刷新为当前最新时间'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if inspect(bind).has_table('users'):
        op.drop_index(op.f('ix_users_username'), table_name='users')
        op.drop_index(op.f('ix_users_id'), table_name='users')
        op.drop_table('users')

    postgresql.ENUM(
        'student',
        'admin',
        name='user_role',
        create_type=False,
    ).drop(bind, checkfirst=True)
