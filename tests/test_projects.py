import subprocess

import httpx
import pytest

from app.main import app

PROJECT_KEYS = {"id", "name", "description"}


def run_alembic(*args: str) -> None:
    subprocess.run(["uv", "run", "alembic", *args], check=True)


@pytest.fixture(autouse=True)
def base_limpia() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")


def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def test_post_project_minimo() -> None:
    async with client() as c:
        response = await c.post("/projects", json={"name": "Casa"})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "Casa", "description": None}


async def test_post_project_con_descripcion() -> None:
    async with client() as c:
        await c.post("/projects", json={"name": "Casa"})
        response = await c.post(
            "/projects", json={"name": "Trabajo", "description": "cosas"}
        )

    assert response.status_code == 201
    assert response.json() == {"id": 2, "name": "Trabajo", "description": "cosas"}


async def test_post_project_name_solo_espacios_es_422() -> None:
    async with client() as c:
        response = await c.post("/projects", json={"name": "   "})

    assert response.status_code == 422
    assert "detail" in response.json()


async def test_post_project_sin_name_es_422() -> None:
    async with client() as c:
        response = await c.post("/projects", json={"description": "x"})

    assert response.status_code == 422
    assert "detail" in response.json()


async def test_get_projects_ordenado_por_id() -> None:
    async with client() as c:
        await c.post("/projects", json={"name": "Casa"})
        await c.post("/projects", json={"name": "Trabajo", "description": "cosas"})
        response = await c.get("/projects")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Casa", "description": None},
        {"id": 2, "name": "Trabajo", "description": "cosas"},
    ]


async def test_get_projects_orden_estable_entre_llamadas() -> None:
    async with client() as c:
        for nombre in ("Casa", "Trabajo", "Estudio"):
            await c.post("/projects", json={"name": nombre})
        primera = await c.get("/projects")
        segunda = await c.get("/projects")

    ids_primera = [p["id"] for p in primera.json()]
    ids_segunda = [p["id"] for p in segunda.json()]
    assert ids_primera == ids_segunda


async def test_get_projects_esquema_exacto() -> None:
    async with client() as c:
        await c.post("/projects", json={"name": "Casa"})
        response = await c.get("/projects")

    for obj in response.json():
        assert set(obj.keys()) == PROJECT_KEYS


async def test_get_project_por_id_existente() -> None:
    async with client() as c:
        creado = await c.post("/projects", json={"name": "Casa"})
        project_id = creado.json()["id"]
        response = await c.get(f"/projects/{project_id}")

    assert response.status_code == 200
    assert response.json() == creado.json()
    assert set(response.json().keys()) == PROJECT_KEYS


async def test_get_project_inexistente_es_404() -> None:
    async with client() as c:
        response = await c.get("/projects/999")

    assert response.status_code == 404
    assert "detail" in response.json()


async def test_patch_project_agrega_descripcion() -> None:
    async with client() as c:
        creado = await c.post("/projects", json={"name": "Casa"})
        project_id = creado.json()["id"]
        response = await c.patch(
            f"/projects/{project_id}", json={"description": "hogar"}
        )
        leido = await c.get(f"/projects/{project_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": project_id,
        "name": "Casa",
        "description": "hogar",
    }
    assert leido.json() == response.json()


async def test_patch_project_recorta_name() -> None:
    async with client() as c:
        creado = await c.post("/projects", json={"name": "Casa"})
        project_id = creado.json()["id"]
        response = await c.patch(
            f"/projects/{project_id}", json={"name": "  Casa nueva  "}
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Casa nueva"


async def test_patch_project_name_vacio_es_422_y_no_cambia() -> None:
    async with client() as c:
        creado = await c.post("/projects", json={"name": "Casa"})
        project_id = creado.json()["id"]
        response = await c.patch(f"/projects/{project_id}", json={"name": "   "})
        leido = await c.get(f"/projects/{project_id}")

    assert response.status_code == 422
    assert "detail" in response.json()
    assert leido.json()["name"] == "Casa"


async def test_patch_project_description_null_explicito() -> None:
    async with client() as c:
        creado = await c.post(
            "/projects", json={"name": "Casa", "description": "hogar"}
        )
        project_id = creado.json()["id"]
        response = await c.patch(
            f"/projects/{project_id}", json={"description": None}
        )

    assert response.status_code == 200
    assert response.json()["description"] is None


async def test_patch_project_inexistente_es_404() -> None:
    async with client() as c:
        response = await c.patch("/projects/999", json={"name": "X"})

    assert response.status_code == 404
    assert "detail" in response.json()


async def test_patch_project_esquema_exacto() -> None:
    async with client() as c:
        creado = await c.post("/projects", json={"name": "Casa"})
        project_id = creado.json()["id"]
        response = await c.patch(
            f"/projects/{project_id}", json={"description": "hogar"}
        )

    assert set(response.json().keys()) == PROJECT_KEYS
