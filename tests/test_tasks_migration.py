import subprocess

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import get_database_url

PROJECTS_REVISION = "e7a3a73c8c3b"


def run_alembic(*args: str) -> None:
    subprocess.run(["uv", "run", "alembic", *args], check=True)


async def _inspect_tasks() -> tuple[bool, set[str], dict[str, bool], set[str]]:
    engine = create_async_engine(get_database_url())
    try:
        async with engine.connect() as connection:
            def read(sync_conn):
                insp = inspect(sync_conn)
                if not insp.has_table("tasks"):
                    return False, set(), {}, set()
                cols = insp.get_columns("tasks")
                names = {c["name"] for c in cols}
                nullable = {c["name"]: c["nullable"] for c in cols}
                referred = {
                    fk["referred_table"] for fk in insp.get_foreign_keys("tasks")
                }
                return True, names, nullable, referred

            return await connection.run_sync(read)
    finally:
        await engine.dispose()


async def table_exists() -> bool:
    exists, _, _, _ = await _inspect_tasks()
    return exists


async def test_tasks_table_missing_before_its_migration() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", PROJECTS_REVISION)
    assert await table_exists() is False


async def test_tasks_migration_creates_and_drops_table() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")

    exists, names, nullable, referred = await _inspect_tasks()
    assert exists is True
    assert {"id", "title", "description", "project_id", "state_id"} <= names
    assert nullable["title"] is False
    assert nullable["project_id"] is False
    assert nullable["state_id"] is False
    assert nullable["description"] is True
    assert {"projects", "states"} <= referred

    run_alembic("downgrade", "base")
    assert await table_exists() is False


async def test_tasks_downgrade_one_step_keeps_projects_and_states() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")
    run_alembic("downgrade", "-1")

    engine = create_async_engine(get_database_url())
    try:
        async with engine.connect() as connection:
            def read(sync_conn):
                insp = inspect(sync_conn)
                return (
                    insp.has_table("tasks"),
                    insp.has_table("projects"),
                    insp.has_table("states"),
                )

            has_tasks, has_projects, has_states = await connection.run_sync(read)
    finally:
        await engine.dispose()

    assert has_tasks is False
    assert has_projects is True
    assert has_states is True

    run_alembic("upgrade", "head")
