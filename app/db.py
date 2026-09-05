import os

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def get_database_url() -> str:
    user = os.environ.get("POSTGRES_USER", "taskflow")
    password = os.environ.get("POSTGRES_PASSWORD", "change_me_local")
    db = os.environ.get("POSTGRES_DB", "taskflow")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


engine: AsyncEngine = create_async_engine(get_database_url())
async_session = async_sessionmaker(engine, expire_on_commit=False)
