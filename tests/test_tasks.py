import subprocess

import httpx
import pytest

from app.main import app

TASK_KEYS = {"id", "title", "description", "project_id", "state_id"}

# state_id según el orden del catálogo sembrado por la migración de states.
STATE_PENDIENTE = 1
STATE_EN_CURSO = 2

# title que "parece válido" pero no deja carácter visible.
TITULOS_SIN_VISIBLE = [
    "",
    "   ",          # espacios ASCII
    "​",       # U+200B ZERO WIDTH SPACE (Cf)
    " ",       # LINE SEPARATOR (Zl)
    " ",       # NO-BREAK SPACE (Zs)
]


def run_alembic(*args: str) -> None:
    subprocess.run(["uv", "run", "alembic", *args], check=True)


@pytest.fixture(autouse=True)
def base_limpia() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")


def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def _crear_proyecto(c: httpx.AsyncClient, name: str) -> int:
    respuesta = await c.post("/projects", json={"name": name})
    return respuesta.json()["id"]


# --- Incremento 3: POST /tasks y GET /tasks sin filtros ---


async def test_post_task_minimo_estado_por_defecto_pendiente() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post("/tasks", json={"title": "Regar", "project_id": 1})

    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id": 1,
        "title": "Regar",
        "description": None,
        "project_id": 1,
        "state_id": STATE_PENDIENTE,
    }


async def test_post_task_con_descripcion_y_estado_explicito() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks",
            json={
                "title": "Podar",
                "description": "el seto",
                "project_id": 1,
                "state_id": STATE_EN_CURSO,
            },
        )

    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id": 1,
        "title": "Podar",
        "description": "el seto",
        "project_id": 1,
        "state_id": STATE_EN_CURSO,
    }


@pytest.mark.parametrize("titulo", TITULOS_SIN_VISIBLE)
async def test_post_task_title_sin_caracter_visible_es_422(titulo: str) -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks", json={"title": titulo, "project_id": 1}
        )

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()


async def test_post_task_sin_title_es_422() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post("/tasks", json={"project_id": 1})

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()


async def test_post_task_sin_project_id_es_422() -> None:
    async with client() as c:
        respuesta = await c.post("/tasks", json={"title": "Regar"})

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()


async def test_post_task_project_id_inexistente_es_422_y_no_crea() -> None:
    async with client() as c:
        respuesta = await c.post(
            "/tasks", json={"title": "Regar", "project_id": 999}
        )
        listado = await c.get("/tasks")

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()
    assert listado.json() == []


async def test_post_task_state_id_inexistente_es_422() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks", json={"title": "Regar", "project_id": 1, "state_id": 99}
        )

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()


async def test_post_task_recorta_title() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks", json={"title": "  Regar  ", "project_id": 1}
        )

    assert respuesta.status_code == 201
    assert respuesta.json()["title"] == "Regar"


async def test_get_tasks_ordenado_por_id() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        await c.post("/tasks", json={"title": "Podar", "project_id": 1})
        respuesta = await c.get("/tasks")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [t["id"] for t in cuerpo] == [1, 2]
    assert [t["title"] for t in cuerpo] == ["Regar", "Podar"]


async def test_get_tasks_orden_estable_entre_llamadas() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        for titulo in ("Regar", "Podar", "Barrer"):
            await c.post("/tasks", json={"title": titulo, "project_id": 1})
        primera = await c.get("/tasks")
        segunda = await c.get("/tasks")

    assert [t["id"] for t in primera.json()] == [t["id"] for t in segunda.json()]


async def test_get_tasks_esquema_exacto() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        respuesta = await c.get("/tasks")

    for obj in respuesta.json():
        assert set(obj.keys()) == TASK_KEYS
        assert "due_at" not in obj


# --- Incremento 4: filtros project_id y state_id ---


async def _sembrar_escenario(c: httpx.AsyncClient) -> None:
    """Dos proyectos; tareas repartidas entre proyectos y estados, en orden fijo.

    id 1: proyecto 1, PENDIENTE
    id 2: proyecto 1, EN_CURSO
    id 3: proyecto 2, PENDIENTE
    id 4: proyecto 2, EN_CURSO
    """
    await _crear_proyecto(c, "Casa")
    await _crear_proyecto(c, "Trabajo")
    await c.post(
        "/tasks",
        json={"title": "t1", "project_id": 1, "state_id": STATE_PENDIENTE},
    )
    await c.post(
        "/tasks",
        json={"title": "t2", "project_id": 1, "state_id": STATE_EN_CURSO},
    )
    await c.post(
        "/tasks",
        json={"title": "t3", "project_id": 2, "state_id": STATE_PENDIENTE},
    )
    await c.post(
        "/tasks",
        json={"title": "t4", "project_id": 2, "state_id": STATE_EN_CURSO},
    )


async def test_get_tasks_filtra_por_project_id() -> None:
    async with client() as c:
        await _sembrar_escenario(c)
        respuesta = await c.get("/tasks", params={"project_id": 1})

    assert respuesta.status_code == 200
    assert [t["id"] for t in respuesta.json()] == [1, 2]


async def test_get_tasks_filtra_por_state_id() -> None:
    async with client() as c:
        await _sembrar_escenario(c)
        respuesta = await c.get("/tasks", params={"state_id": STATE_EN_CURSO})

    assert respuesta.status_code == 200
    assert [t["id"] for t in respuesta.json()] == [2, 4]


async def test_get_tasks_filtros_combinados() -> None:
    async with client() as c:
        await _sembrar_escenario(c)
        respuesta = await c.get(
            "/tasks",
            params={"project_id": 1, "state_id": STATE_PENDIENTE},
        )

    assert respuesta.status_code == 200
    assert [t["id"] for t in respuesta.json()] == [1]


async def test_get_tasks_filtro_sin_coincidencias_es_lista_vacia() -> None:
    async with client() as c:
        await _sembrar_escenario(c)
        respuesta = await c.get("/tasks", params={"project_id": 999})

    assert respuesta.status_code == 200
    assert respuesta.json() == []


async def test_get_tasks_filtro_no_entero_es_422() -> None:
    async with client() as c:
        await _sembrar_escenario(c)
        respuesta = await c.get("/tasks", params={"state_id": "abc"})

    assert respuesta.status_code == 422


async def test_get_tasks_orden_estable_con_filtro() -> None:
    async with client() as c:
        await _sembrar_escenario(c)
        primera = await c.get("/tasks", params={"project_id": 2})
        segunda = await c.get("/tasks", params={"project_id": 2})

    assert [t["id"] for t in primera.json()] == [t["id"] for t in segunda.json()]


async def test_get_tasks_filtrado_esquema_exacto() -> None:
    async with client() as c:
        await _sembrar_escenario(c)
        respuesta = await c.get("/tasks", params={"project_id": 1})

    for obj in respuesta.json():
        assert set(obj.keys()) == TASK_KEYS


# --- Incremento 5: GET /tasks/{id} ---


async def test_get_task_por_id_existente() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.get(f"/tasks/{task_id}")

    assert respuesta.status_code == 200
    assert respuesta.json() == creado.json()
    assert set(respuesta.json().keys()) == TASK_KEYS


async def test_get_task_inexistente_es_404() -> None:
    async with client() as c:
        respuesta = await c.get("/tasks/999")

    assert respuesta.status_code == 404
    assert "detail" in respuesta.json()


# --- Incremento 6: PATCH /tasks/{id} ---


async def test_patch_task_cambia_estado() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(
            f"/tasks/{task_id}", json={"state_id": STATE_EN_CURSO}
        )
        leido = await c.get(f"/tasks/{task_id}")

    assert respuesta.status_code == 200
    assert respuesta.json()["state_id"] == STATE_EN_CURSO
    assert leido.json() == respuesta.json()


async def test_patch_task_recorta_title() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(
            f"/tasks/{task_id}", json={"title": "  Regar más  "}
        )

    assert respuesta.status_code == 200
    assert respuesta.json()["title"] == "Regar más"


async def test_patch_task_title_sin_visible_es_422_y_no_cambia() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(f"/tasks/{task_id}", json={"title": "​"})
        leido = await c.get(f"/tasks/{task_id}")

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()
    assert leido.json()["title"] == "Regar"


async def test_patch_task_description_null_explicito() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post(
            "/tasks",
            json={"title": "Regar", "description": "con la manguera", "project_id": 1},
        )
        task_id = creado.json()["id"]
        respuesta = await c.patch(
            f"/tasks/{task_id}", json={"description": None}
        )

    assert respuesta.status_code == 200
    assert respuesta.json()["description"] is None


async def test_patch_task_cambia_project_id_existente() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        await _crear_proyecto(c, "Trabajo")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(f"/tasks/{task_id}", json={"project_id": 2})

    assert respuesta.status_code == 200
    assert respuesta.json()["project_id"] == 2


async def test_patch_task_project_id_inexistente_es_422() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(f"/tasks/{task_id}", json={"project_id": 999})

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()


async def test_patch_task_state_id_inexistente_es_422() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(f"/tasks/{task_id}", json={"state_id": 99})

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()


async def test_patch_task_inexistente_es_404() -> None:
    async with client() as c:
        respuesta = await c.patch("/tasks/999", json={"title": "X"})

    assert respuesta.status_code == 404
    assert "detail" in respuesta.json()


async def test_patch_task_esquema_exacto() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(
            f"/tasks/{task_id}", json={"description": "hogar"}
        )

    assert set(respuesta.json().keys()) == TASK_KEYS


# --- Incremento 7: DELETE /tasks/{id} ---


async def test_delete_task_existente_es_204_sin_cuerpo() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.delete(f"/tasks/{task_id}")
        leido = await c.get(f"/tasks/{task_id}")
        listado = await c.get("/tasks")

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert leido.status_code == 404
    assert listado.json() == []


async def test_delete_task_inexistente_es_404() -> None:
    async with client() as c:
        respuesta = await c.delete("/tasks/999")

    assert respuesta.status_code == 404
    assert "detail" in respuesta.json()


async def test_delete_task_no_afecta_al_proyecto() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        await c.delete(f"/tasks/{task_id}")
        proyecto = await c.get("/projects/1")

    assert proyecto.status_code == 200
