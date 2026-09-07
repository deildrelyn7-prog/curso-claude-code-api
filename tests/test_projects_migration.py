import subprocess

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import get_database_url

STATES_REVISION = "306b627a3936"


def run_alembic(*args: str) -> None:
    subprocess.run(["uv", "run", "alembic", *args], check=True)


async def _inspect_projects() -> tuple[bool, set[str], dict[str, bool]]:
    engine = create_async_engine(get_database_url())
    try:
        async with engine.connect() as connection:
            def read(sync_conn):
                insp = inspect(sync_conn)
                if not insp.has_table("projects"):
                    return False, set(), {}
                cols = insp.get_columns("projects")
                names = {c["name"] for c in cols}
                nullable = {c["name"]: c["nullable"] for c in cols}
                return True, names, nullable

            return await connection.run_sync(read)
    finally:
        await engine.dispose()


async def table_exists() -> bool:
    exists, _, _ = await _inspect_projects()
    return exists


async def test_projects_table_missing_before_its_migration() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", STATES_REVISION)
    assert await table_exists() is False


async def test_projects_migration_creates_and_drops_table() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")

    exists, names, nullable = await _inspect_projects()
    assert exists is True
    assert {"id", "name", "description"} <= names
    assert nullable["name"] is False
    assert nullable["description"] is True

    run_alembic("downgrade", "base")
    assert await table_exists() is False


async def test_projects_downgrade_one_step_keeps_states() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")
    run_alembic("downgrade", "-1")

    engine = create_async_engine(get_database_url())
    try:
        async with engine.connect() as connection:
            def read(sync_conn):
                insp = inspect(sync_conn)
                return insp.has_table("projects"), insp.has_table("states")

            has_projects, has_states = await connection.run_sync(read)
    finally:
        await engine.dispose()

    assert has_projects is False
    assert has_states is True

    run_alembic("upgrade", "head")
