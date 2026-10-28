import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Task, TaskStatus
from app.infrastructure.db.models import ProjectModel, TaskModel

InsertTask = Callable[..., Awaitable[Task]]
SessionFactory = async_sessionmaker[AsyncSession]


async def create_project(client: AsyncClient, **body: Any) -> Response:
    return await client.post("/projects", json={"name": "Alpha", **body})


async def count_projects(session_factory: SessionFactory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(ProjectModel))


async def task_ids(session_factory: SessionFactory, project_id: str) -> set[uuid.UUID]:
    async with session_factory() as session:
        result = await session.scalars(
            select(TaskModel.id).where(TaskModel.project_id == uuid.UUID(project_id))
        )
        return set(result)


async def test_create_project(client: AsyncClient) -> None:
    response = await create_project(client, description="Первый проект")

    assert response.status_code == 201
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["name"] == "Alpha"
    assert body["description"] == "Первый проект"
    assert body["created_at"]


async def test_create_project_without_description(client: AsyncClient) -> None:
    response = await client.post("/projects", json={"name": "Alpha"})

    assert response.status_code == 201
    assert response.json()["description"] is None


async def test_create_project_strips_whitespace(client: AsyncClient) -> None:
    response = await client.post(
        "/projects", json={"name": "  Alpha  ", "description": "   "}
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Alpha"
    assert response.json()["description"] is None


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"name": "ab"}, id="too-short"),
        pytest.param({"name": "  ab  "}, id="too-short-after-strip"),
        pytest.param({"name": "a" * 101}, id="too-long"),
        pytest.param({}, id="missing"),
        pytest.param({"name": 123}, id="not-a-string"),
        pytest.param(
            {"name": "Alpha", "description": "d" * 1001}, id="long-description"
        ),
    ],
)
async def test_create_project_rejects_invalid_data(
    client: AsyncClient, session_factory: SessionFactory, body: dict[str, Any]
) -> None:
    response = await client.post("/projects", json=body)

    assert response.status_code == 422
    assert await count_projects(session_factory) == 0


@pytest.mark.parametrize("length", [3, 100])
async def test_create_project_with_boundary_name_length(
    client: AsyncClient, length: int
) -> None:
    response = await client.post("/projects", json={"name": "a" * length})

    assert response.status_code == 201


async def test_create_project_with_max_description(client: AsyncClient) -> None:
    response = await create_project(client, description="d" * 1000)

    assert response.status_code == 201


@pytest.mark.parametrize("duplicate", ["ALPHA", "  alpha "])
async def test_create_project_with_taken_name(
    client: AsyncClient, session_factory: SessionFactory, duplicate: str
) -> None:
    original = (await create_project(client)).json()

    response = await client.post("/projects", json={"name": duplicate})

    assert response.status_code == 409
    assert await count_projects(session_factory) == 1
    assert (await client.get(f"/projects/{original['id']}")).json() == original


async def test_get_project(client: AsyncClient) -> None:
    created = (await create_project(client, description="Описание")).json()

    response = await client.get(f"/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_unknown_project_is_not_found(client: AsyncClient, method: str) -> None:
    response = await client.request(method, f"/projects/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["GET", "DELETE"])
async def test_invalid_project_id(client: AsyncClient, method: str) -> None:
    response = await client.request(method, "/projects/not-a-uuid")

    assert response.status_code == 422


async def test_delete_project(client: AsyncClient) -> None:
    project_id = (await create_project(client)).json()["id"]

    response = await client.delete(f"/projects/{project_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(f"/projects/{project_id}")).status_code == 404


async def test_name_is_released_after_delete(client: AsyncClient) -> None:
    project_id = (await create_project(client)).json()["id"]
    await client.delete(f"/projects/{project_id}")

    response = await client.post("/projects", json={"name": "alpha"})

    assert response.status_code == 201


async def test_delete_project_with_task_in_progress(
    client: AsyncClient, session_factory: SessionFactory, insert_task: InsertTask
) -> None:
    project_id = (await create_project(client)).json()["id"]
    task = await insert_task(uuid.UUID(project_id), status=TaskStatus.IN_PROGRESS)

    response = await client.delete(f"/projects/{project_id}")

    assert response.status_code == 409
    assert (await client.get(f"/projects/{project_id}")).status_code == 200
    assert await task_ids(session_factory, project_id) == {task.id}


async def test_delete_project_removes_its_tasks(
    client: AsyncClient, session_factory: SessionFactory, insert_task: InsertTask
) -> None:
    project_id = (await create_project(client)).json()["id"]
    await insert_task(uuid.UUID(project_id), "Todo task", TaskStatus.TO_DO)
    await insert_task(uuid.UUID(project_id), "Done task", TaskStatus.DONE)

    response = await client.delete(f"/projects/{project_id}")

    assert response.status_code == 204
    assert await task_ids(session_factory, project_id) == set()


async def test_delete_project_keeps_tasks_of_other_projects(
    client: AsyncClient, session_factory: SessionFactory, insert_task: InsertTask
) -> None:
    project_a = (await create_project(client)).json()["id"]
    project_b = (await client.post("/projects", json={"name": "Beta"})).json()["id"]
    await insert_task(uuid.UUID(project_a), "Task A")
    task_b = await insert_task(uuid.UUID(project_b), "Task B")

    response = await client.delete(f"/projects/{project_a}")

    assert response.status_code == 204
    assert await task_ids(session_factory, project_b) == {task_b.id}
