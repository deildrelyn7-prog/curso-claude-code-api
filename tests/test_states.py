import httpx

from app.main import app

EXPECTED_STATES = [
    {"id": 1, "code": "PENDIENTE"},
    {"id": 2, "code": "EN_CURSO"},
    {"id": 3, "code": "BLOQUEADA"},
    {"id": 4, "code": "HECHA"},
]


async def test_states_returns_ordered_catalog() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/states")

    assert response.status_code == 200
    assert response.json() == EXPECTED_STATES
