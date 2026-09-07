import subprocess

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import get_database_url

EXPECTED_CODES = {"PENDIENTE", "EN_CURSO", "BLOQUEADA", "HECHA"}


def run_alembic(*args: str) -> None:
    subprocess.run(["uv", "run", "alembic", *args], check=True)


async def table_exists() -> bool:
    engine = create_async_engine(get_database_url())
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync_conn: inspect(sync_conn).has_table("states")
            )
    finally:
        await engine.dispose()


async def fetch_codes() -> list[str]:
    engine = create_async_engine(get_database_url())
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT code FROM states"))
            return [row[0] for row in result.fetchall()]
    finally:
        await engine.dispose()


async def test_states_table_missing_before_migration() -> None:
    run_alembic("downgrade", "base")
    assert await table_exists() is False


async def test_migration_seeds_states_and_is_idempotent() -> None:
    run_alembic("downgrade", "base")

    run_alembic("upgrade", "head")
    assert await table_exists() is True

    codes = await fetch_codes()
    assert set(codes) == EXPECTED_CODES

    run_alembic("upgrade", "head")
    codes_after_second_upgrade = await fetch_codes()
    assert len(codes_after_second_upgrade) == 4

    run_alembic("downgrade", "base")
    assert await table_exists() is False
