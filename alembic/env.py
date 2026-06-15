from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

# 显式导入模型模块，确保 Alembic 能读取所有 ORM 表结构。
from app.models import user  # noqa: F401
from app.models import study_target  # noqa: F401
from app.models import material  # noqa: F401
from app.models import material_structure  # noqa: F401
from app.models import qa  # noqa: F401
from app.models import parse_task  # noqa: F401
from app.models import admin_log  # noqa: F401
from app.models import question  # noqa: F401
from app.models import test_record  # noqa: F401
from app.models import wrong_question  # noqa: F401
from app.models import review_plan  # noqa: F401
from app.models import knowledge  # noqa: F401
from app.models import knowledge_point  # noqa: F401
from app.models import ai_call_log  # noqa: F401

config = context.config

# 使用项目配置中的数据库连接地址，避免在 alembic.ini 中重复维护。
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 自动生成迁移时读取这里的 metadata。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式执行迁移。

    离线模式不会连接数据库，主要用于生成 SQL 脚本。
    """
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在同步连接上下文中执行迁移。

    Alembic 的核心迁移 API 是同步的，异步连接会通过 run_sync 切入这里。
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式执行异步迁移。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口。"""
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
