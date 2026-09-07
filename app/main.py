from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Project, State

app = FastAPI(title="TaskFlow API")


def _clean_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("name no puede quedar vacío")
    return stripped


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


def _serialize(project: Project) -> dict[str, object]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
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
