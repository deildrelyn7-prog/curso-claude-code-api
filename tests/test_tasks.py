import subprocess
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.main import app

TASK_KEYS = {"id", "title", "description", "project_id", "state_id", "due_at"}

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
        "due_at": None,
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
        "due_at": None,
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
        assert "due_at" in obj


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


# --- Tareas v2: due_at ---

STATE_HECHA = 4


async def test_post_task_sin_due_at_lo_devuelve_null() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post("/tasks", json={"title": "Regar", "project_id": 1})

    assert respuesta.status_code == 201
    assert respuesta.json()["due_at"] is None


async def test_post_task_con_due_at_utc_se_conserva() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks",
            json={
                "title": "Regar",
                "project_id": 1,
                "due_at": "2026-03-01T09:00:00Z",
            },
        )

    assert respuesta.status_code == 201
    assert respuesta.json()["due_at"] == "2026-03-01T09:00:00Z"


async def test_post_task_con_due_at_con_offset_se_normaliza_a_utc() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks",
            json={
                "title": "Regar",
                "project_id": 1,
                "due_at": "2026-03-01T09:00:00+02:00",
            },
        )

    assert respuesta.status_code == 201
    assert respuesta.json()["due_at"] == "2026-03-01T07:00:00Z"


async def test_post_task_due_at_sin_zona_es_422() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks",
            json={
                "title": "Regar",
                "project_id": 1,
                "due_at": "2026-03-01T09:00:00",
            },
        )

    assert respuesta.status_code == 422
    assert "detail" in respuesta.json()


async def test_post_task_due_at_se_serializa_sin_microsegundos() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks",
            json={
                "title": "Regar",
                "project_id": 1,
                "due_at": "2026-03-01T09:00:00.123456Z",
            },
        )

    assert respuesta.status_code == 201
    assert respuesta.json()["due_at"] == "2026-03-01T09:00:00Z"


async def test_patch_task_fija_due_at() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post("/tasks", json={"title": "Regar", "project_id": 1})
        task_id = creado.json()["id"]
        respuesta = await c.patch(
            f"/tasks/{task_id}", json={"due_at": "2026-03-01T09:00:00Z"}
        )
        leido = await c.get(f"/tasks/{task_id}")

    assert respuesta.status_code == 200
    assert respuesta.json()["due_at"] == "2026-03-01T09:00:00Z"
    assert leido.json() == respuesta.json()


async def test_patch_task_limpia_due_at_con_null() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post(
            "/tasks",
            json={
                "title": "Regar",
                "project_id": 1,
                "due_at": "2026-03-01T09:00:00Z",
            },
        )
        task_id = creado.json()["id"]
        respuesta = await c.patch(f"/tasks/{task_id}", json={"due_at": None})

    assert respuesta.status_code == 200
    assert respuesta.json()["due_at"] is None


async def test_patch_task_due_at_sin_zona_es_422_y_no_cambia() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        creado = await c.post(
            "/tasks",
            json={
                "title": "Regar",
                "project_id": 1,
                "due_at": "2026-03-01T09:00:00Z",
            },
        )
        task_id = creado.json()["id"]
        respuesta = await c.patch(
            f"/tasks/{task_id}", json={"due_at": "2027-01-01T00:00:00"}
        )
        leido = await c.get(f"/tasks/{task_id}")

    assert respuesta.status_code == 422
    assert leido.json()["due_at"] == "2026-03-01T09:00:00Z"


async def test_post_task_due_at_esquema_exacto() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.post(
            "/tasks",
            json={
                "title": "Regar",
                "project_id": 1,
                "due_at": "2026-03-01T09:00:00Z",
            },
        )

    assert set(respuesta.json().keys()) == TASK_KEYS


# --- Tareas v2: filtro overdue ---


async def _sembrar_overdue(c: httpx.AsyncClient) -> None:
    """Cuatro tareas en un proyecto:

    id 1: vencida (due_at en el pasado), PENDIENTE     -> overdue
    id 2: futura (due_at por delante), PENDIENTE       -> no
    id 3: sin due_at, PENDIENTE                        -> no
    id 4: vencida, HECHA                               -> no
    """
    await _crear_proyecto(c, "Casa")
    pasado = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    futuro = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    await c.post(
        "/tasks",
        json={"title": "vencida", "project_id": 1, "due_at": pasado},
    )
    await c.post(
        "/tasks",
        json={"title": "futura", "project_id": 1, "due_at": futuro},
    )
    await c.post("/tasks", json={"title": "sin fecha", "project_id": 1})
    await c.post(
        "/tasks",
        json={
            "title": "vencida hecha",
            "project_id": 1,
            "state_id": STATE_HECHA,
            "due_at": pasado,
        },
    )


async def test_get_tasks_overdue_true_devuelve_solo_vencidas_no_hechas() -> None:
    async with client() as c:
        await _sembrar_overdue(c)
        respuesta = await c.get("/tasks", params={"overdue": "true"})

    assert respuesta.status_code == 200
    assert [t["id"] for t in respuesta.json()] == [1]


async def test_get_tasks_overdue_false_no_filtra() -> None:
    async with client() as c:
        await _sembrar_overdue(c)
        respuesta = await c.get("/tasks", params={"overdue": "false"})

    assert respuesta.status_code == 200
    assert [t["id"] for t in respuesta.json()] == [1, 2, 3, 4]


async def test_get_tasks_overdue_omitido_no_filtra() -> None:
    async with client() as c:
        await _sembrar_overdue(c)
        respuesta = await c.get("/tasks")

    assert [t["id"] for t in respuesta.json()] == [1, 2, 3, 4]


async def test_get_tasks_overdue_combina_con_project_id() -> None:
    async with client() as c:
        await _sembrar_overdue(c)
        await _crear_proyecto(c, "Otro")
        pasado = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        await c.post(
            "/tasks",
            json={"title": "vencida otro", "project_id": 2, "due_at": pasado},
        )
        respuesta = await c.get(
            "/tasks", params={"overdue": "true", "project_id": 1}
        )

    assert [t["id"] for t in respuesta.json()] == [1]


async def test_get_tasks_overdue_orden_estable() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        pasado = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for titulo in ("a", "b", "c"):
            await c.post(
                "/tasks",
                json={"title": titulo, "project_id": 1, "due_at": pasado},
            )
        primera = await c.get("/tasks", params={"overdue": "true"})
        segunda = await c.get("/tasks", params={"overdue": "true"})

    assert [t["id"] for t in primera.json()] == [t["id"] for t in segunda.json()]


async def test_get_tasks_overdue_no_entero_es_422() -> None:
    async with client() as c:
        await _crear_proyecto(c, "Casa")
        respuesta = await c.get("/tasks", params={"overdue": "quiza"})

    assert respuesta.status_code == 422
