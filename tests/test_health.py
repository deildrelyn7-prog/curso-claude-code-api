import httpx

from app.main import app


async def test_health_returns_ok() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_no_expone_detalles_internos() -> None:
    """docs/contrato-api.md, sección Salud: "No expone credenciales ni
    detalles internos." El único campo permitido es `status`."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert set(response.json().keys()) == {"status"}
