from sqlalchemy import text

from app.db import get_engine


async def test_engine_connects_to_database() -> None:
    engine = get_engine()
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        assert result.scalar() == 1
