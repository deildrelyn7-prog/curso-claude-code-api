from fastapi import FastAPI
from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import State

app = FastAPI(title="TaskFlow API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/states")
async def list_states() -> list[dict[str, object]]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        result = await session.execute(
            select(State).order_by(State.sort_order, State.id)
        )
        states = result.scalars().all()
    return [{"id": state.id, "code": state.code} for state in states]
