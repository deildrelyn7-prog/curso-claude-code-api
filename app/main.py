import unicodedata
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Project, State, Task

app = FastAPI(title="TaskFlow API")

DEFAULT_STATE_CODE = "PENDIENTE"
DONE_STATE_CODE = "HECHA"

# Categorías Unicode sin carácter visible: control, formato, separadores de
# línea, de párrafo y de espacio.
_INVISIBLE_CATEGORIES = {"Cc", "Cf", "Zl", "Zp", "Zs"}


def _clean_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("name no puede quedar vacío")
    return stripped


def _clean_title(value: str) -> str:
    stripped = value.strip()
    if not stripped or all(
        unicodedata.category(ch) in _INVISIBLE_CATEGORIES for ch in stripped
    ):
        raise ValueError("title no puede quedar sin carácter visible")
    return stripped


def _clean_due_at(value: datetime) -> datetime:
    """Rechaza una fecha sin zona y la normaliza a UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("due_at debe incluir zona horaria")
    return value.astimezone(UTC)


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_no_vacio(cls, value: str) -> str:
        return _clean_name(value)


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_no_vacio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_name(value)


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: int
    state_id: int | None = None
    due_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_visible(cls, value: str) -> str:
        return _clean_title(value)

    @field_validator("due_at")
    @classmethod
    def due_at_con_zona(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _clean_due_at(value)


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    project_id: int | None = None
    state_id: int | None = None
    due_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_visible(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_title(value)

    @field_validator("due_at")
    @classmethod
    def due_at_con_zona(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _clean_due_at(value)


def _serialize(project: Project) -> dict[str, object]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
    }


def _serialize_due_at(value: datetime | None) -> str | None:
    """UTC, sufijo `Z`, sin microsegundos: 2026-03-01T09:00:00Z."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _serialize_task(task: Task) -> dict[str, object]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "project_id": task.project_id,
        "state_id": task.state_id,
        "due_at": _serialize_due_at(task.due_at),
    }


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


@app.post("/projects", status_code=201)
async def create_project(payload: ProjectCreate) -> dict[str, object]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        project = Project(name=payload.name, description=payload.description)
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return _serialize(project)


@app.get("/projects")
async def list_projects() -> list[dict[str, object]]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        result = await session.execute(select(Project).order_by(Project.id))
        projects = result.scalars().all()
    return [_serialize(project) for project in projects]


@app.get("/projects/{project_id}")
async def get_project(project_id: int) -> dict[str, object]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="proyecto no encontrado")
    return _serialize(project)


@app.patch("/projects/{project_id}")
async def patch_project(project_id: int, payload: ProjectPatch) -> dict[str, object]:
    campos = payload.model_fields_set
    async_session = get_sessionmaker()
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="proyecto no encontrado")
        if "name" in campos:
            project.name = payload.name
        if "description" in campos:
            project.description = payload.description
        await session.commit()
        await session.refresh(project)
        return _serialize(project)


@app.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: int) -> None:
    async_session = get_sessionmaker()
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="proyecto no encontrado")
        tiene_tareas = await session.execute(
            select(Task.id).where(Task.project_id == project_id).limit(1)
        )
        if tiene_tareas.first() is not None:
            raise HTTPException(
                status_code=409, detail="el proyecto tiene tareas asociadas"
            )
        await session.delete(project)
        await session.commit()


async def _resolver_state_id(session, state_id: int | None) -> int:
    """Devuelve el state_id a usar: el enviado (si existe) o el de PENDIENTE."""
    if state_id is None:
        result = await session.execute(
            select(State.id).where(State.code == DEFAULT_STATE_CODE)
        )
        return result.scalar_one()
    existe = await session.get(State, state_id)
    if existe is None:
        raise HTTPException(status_code=422, detail="state_id no existe")
    return state_id


async def _validar_project_id(session, project_id: int) -> None:
    if await session.get(Project, project_id) is None:
        raise HTTPException(status_code=422, detail="project_id no existe")


@app.post("/tasks", status_code=201)
async def create_task(payload: TaskCreate) -> dict[str, object]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        await _validar_project_id(session, payload.project_id)
        state_id = await _resolver_state_id(session, payload.state_id)
        task = Task(
            title=payload.title,
            description=payload.description,
            project_id=payload.project_id,
            state_id=state_id,
            due_at=payload.due_at,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return _serialize_task(task)


@app.get("/tasks")
async def list_tasks(
    project_id: int | None = None,
    state_id: int | None = None,
    overdue: bool | None = None,
) -> list[dict[str, object]]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        query = select(Task)
        if project_id is not None:
            query = query.where(Task.project_id == project_id)
        if state_id is not None:
            query = query.where(Task.state_id == state_id)
        if overdue:
            done = select(State.id).where(State.code == DONE_STATE_CODE).scalar_subquery()
            query = query.where(
                Task.due_at.is_not(None),
                Task.due_at < datetime.now(UTC),
                Task.state_id != done,
            )
        query = query.order_by(Task.id)
        result = await session.execute(query)
        tasks = result.scalars().all()
    return [_serialize_task(task) for task in tasks]


@app.get("/tasks/{task_id}")
async def get_task(task_id: int) -> dict[str, object]:
    async_session = get_sessionmaker()
    async with async_session() as session:
        task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="tarea no encontrada")
    return _serialize_task(task)


@app.patch("/tasks/{task_id}")
async def patch_task(task_id: int, payload: TaskPatch) -> dict[str, object]:
    campos = payload.model_fields_set
    async_session = get_sessionmaker()
    async with async_session() as session:
        task = await session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="tarea no encontrada")
        if "project_id" in campos:
            if payload.project_id is None:
                raise HTTPException(status_code=422, detail="project_id no puede ser null")
            await _validar_project_id(session, payload.project_id)
            task.project_id = payload.project_id
        if "state_id" in campos:
            if payload.state_id is None:
                raise HTTPException(status_code=422, detail="state_id no puede ser null")
            task.state_id = await _resolver_state_id(session, payload.state_id)
        if "title" in campos:
            task.title = payload.title
        if "description" in campos:
            task.description = payload.description
        if "due_at" in campos:
            task.due_at = payload.due_at
        await session.commit()
        await session.refresh(task)
        return _serialize_task(task)


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int) -> None:
    async_session = get_sessionmaker()
    async with async_session() as session:
        task = await session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="tarea no encontrada")
        await session.delete(task)
        await session.commit()
