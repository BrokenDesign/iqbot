import asyncio

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context
from iqbot.config import settings
from iqbot.db import Base

config = context.config

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.database.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable: AsyncEngine = create_async_engine(
        settings.database.url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:

        def do_configure(sync_conn: Connection) -> None:
            context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
                compare_type=True,
                render_as_batch=True,
            )

        await connection.run_sync(do_configure)
        await connection.run_sync(lambda _: context.run_migrations())

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
