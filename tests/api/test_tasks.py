import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Task, TaskStatus
from app.infrastructure.db.models import TaskModel

InsertTask = Callable[..., Awaitable[Task]]
SessionFactory = async_sessionmaker[AsyncSession]


async def create_project(client: AsyncClient, name: str = "Alpha") -> str:
    response = await client.post("/projects", json={"name": name})
    return response.json()["id"]


async def create_task(
    client: AsyncClient, project_id: str, title: str = "Write spec", **body: Any
) -> dict[str, Any]:
    response = await client.post(
        f"/projects/{project_id}/tasks", json={"title": title, **body}
    )
    assert response.status_code == 201
    return response.json()


async def get_task(client: AsyncClient, task_id: str) -> dict[str, Any]:
    response = await client.get(f"/tasks/{task_id}")
    return response.json()


async def count_tasks(session_factory: SessionFactory) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(TaskModel))


async def backdate_task(
    client: AsyncClient, session_factory: SessionFactory, task_id: str
) -> dict[str, Any]:
    async with session_factory() as session:
        await session.execute(
            update(TaskModel)
            .where(TaskModel.id == uuid.UUID(task_id))
            .values(updated_at=TaskModel.updated_at - timedelta(hours=1))
        )
        await session.commit()
    return await get_task(client, task_id)


def updated_at(task: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(task["updated_at"])


@pytest.fixture
async def project_id(client: AsyncClient) -> str:
    return await create_project(client)


@pytest.fixture
async def task(client: AsyncClient, project_id: str) -> dict[str, Any]:
    return await create_task(client, project_id)


@pytest.fixture
async def done_task(
    client: AsyncClient, project_id: str, insert_task: InsertTask
) -> dict[str, Any]:
    inserted = await insert_task(uuid.UUID(project_id), "Write spec", TaskStatus.DONE)
    return await get_task(client, str(inserted.id))


async def test_create_task(client: AsyncClient, project_id: str) -> None:
    response = await client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Write spec", "priority": "high"},
    )

    assert response.status_code == 201
    body = response.json()
    assert uuid.UUID(body["id"])
    assert body["project_id"] == project_id
    assert body["title"] == "Write spec"
    assert body["priority"] == "high"
    assert body["status"] == "todo"
    assert body["created_at"]
    assert body["updated_at"]


async def test_create_task_with_default_priority(
    client: AsyncClient, project_id: str
) -> None:
    body = await create_task(client, project_id)

    assert body["priority"] == "medium"


async def test_create_task_strips_title(client: AsyncClient, project_id: str) -> None:
    body = await create_task(client, project_id, "  Write spec  ")

    assert body["title"] == "Write spec"


async def test_create_task_rejects_status(
    client: AsyncClient, session_factory: SessionFactory, project_id: str
) -> None:
    response = await client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Write spec", "status": "done"},
    )

    assert response.status_code == 422
    assert await count_tasks(session_factory) == 0


async def test_create_task_in_unknown_project(
    client: AsyncClient, session_factory: SessionFactory
) -> None:
    response = await client.post(
        f"/projects/{uuid.uuid4()}/tasks", json={"title": "Write spec"}
    )

    assert response.status_code == 404
    assert await count_tasks(session_factory) == 0


async def test_create_task_with_invalid_project_id(client: AsyncClient) -> None:
    response = await client.post(
        "/projects/not-a-uuid/tasks", json={"title": "Write spec"}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"title": "ab"}, id="too-short"),
        pytest.param({"title": "  ab  "}, id="too-short-after-strip"),
        pytest.param({"title": "a" * 201}, id="too-long"),
        pytest.param({}, id="missing"),
        pytest.param({"title": 123}, id="not-a-string"),
        pytest.param({"title": "Write spec", "priority": "urgent"}, id="bad-priority"),
    ],
)
async def test_create_task_rejects_invalid_data(
    client: AsyncClient,
    session_factory: SessionFactory,
    project_id: str,
    body: dict[str, Any],
) -> None:
    response = await client.post(f"/projects/{project_id}/tasks", json=body)

    assert response.status_code == 422
    assert await count_tasks(session_factory) == 0


@pytest.mark.parametrize("length", [3, 200])
async def test_create_task_with_boundary_title_length(
    client: AsyncClient, project_id: str, length: int
) -> None:
    response = await client.post(
        f"/projects/{project_id}/tasks", json={"title": "a" * length}
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"title": "ab"}, id="short-title"),
        pytest.param({"priority": "urgent"}, id="bad-priority"),
    ],
)
async def test_update_task_rejects_invalid_data(
    client: AsyncClient, task: dict[str, Any], body: dict[str, Any]
) -> None:
    response = await client.patch(f"/tasks/{task['id']}", json=body)

    assert response.status_code == 422
    assert await get_task(client, task["id"]) == task


async def test_create_task_with_taken_title(
    client: AsyncClient,
    session_factory: SessionFactory,
    project_id: str,
    task: dict[str, Any],
) -> None:
    response = await client.post(
        f"/projects/{project_id}/tasks", json={"title": "  WRITE SPEC "}
    )

    assert response.status_code == 409
    assert await count_tasks(session_factory) == 1


async def test_same_title_in_different_projects(
    client: AsyncClient, task: dict[str, Any]
) -> None:
    other_project_id = await create_project(client, "Beta")

    response = await client.post(
        f"/projects/{other_project_id}/tasks", json={"title": "Write spec"}
    )

    assert response.status_code == 201


async def test_update_task_to_taken_title(
    client: AsyncClient, project_id: str, task: dict[str, Any]
) -> None:
    other = await create_task(client, project_id, "Review spec")

    response = await client.patch(f"/tasks/{other['id']}", json={"title": "write spec"})

    assert response.status_code == 409
    assert (await get_task(client, other["id"]))["title"] == "Review spec"


async def test_update_task_title_case(
    client: AsyncClient, task: dict[str, Any]
) -> None:
    response = await client.patch(f"/tasks/{task['id']}", json={"title": "WRITE SPEC"})

    assert response.status_code == 200
    assert response.json()["title"] == "WRITE SPEC"


async def test_get_task(client: AsyncClient, task: dict[str, Any]) -> None:
    response = await client.get(f"/tasks/{task['id']}")

    assert response.status_code == 200
    assert response.json() == task


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        pytest.param("GET", "/tasks/{id}", None, id="get"),
        pytest.param("PATCH", "/tasks/{id}", {"priority": "high"}, id="patch"),
        pytest.param(
            "POST", "/tasks/{id}/status", {"status": "in_progress"}, id="status"
        ),
    ],
)
async def test_unknown_task_is_not_found(
    client: AsyncClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = await client.request(method, path.format(id=uuid.uuid4()), json=body)

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        pytest.param("GET", "/tasks/not-a-uuid", None, id="get"),
        pytest.param("PATCH", "/tasks/not-a-uuid", {"priority": "high"}, id="patch"),
        pytest.param(
            "POST", "/tasks/not-a-uuid/status", {"status": "in_progress"}, id="status"
        ),
    ],
)
async def test_invalid_task_id(
    client: AsyncClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = await client.request(method, path, json=body)

    assert response.status_code == 422


async def test_update_task_title(
    client: AsyncClient, session_factory: SessionFactory, project_id: str
) -> None:
    created = await create_task(client, project_id, priority="low")
    before = await backdate_task(client, session_factory, created["id"])

    response = await client.patch(
        f"/tasks/{created['id']}", json={"title": "  Write tests "}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Write tests"
    assert body["priority"] == "low"
    assert updated_at(body) > updated_at(before)


async def test_update_task_priority(client: AsyncClient, task: dict[str, Any]) -> None:
    response = await client.patch(f"/tasks/{task['id']}", json={"priority": "high"})

    assert response.status_code == 200
    assert response.json()["priority"] == "high"
    assert response.json()["title"] == task["title"]


async def test_update_task_title_and_priority(
    client: AsyncClient, task: dict[str, Any]
) -> None:
    response = await client.patch(
        f"/tasks/{task['id']}", json={"title": "Write tests", "priority": "low"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Write tests"
    assert response.json()["priority"] == "low"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="empty"),
        pytest.param({"title": None, "priority": None}, id="nulls"),
    ],
)
async def test_empty_update_is_rejected(
    client: AsyncClient,
    session_factory: SessionFactory,
    task: dict[str, Any],
    body: dict[str, Any],
) -> None:
    before = await backdate_task(client, session_factory, task["id"])

    response = await client.patch(f"/tasks/{task['id']}", json=body)

    assert response.status_code == 422
    assert await get_task(client, task["id"]) == before


async def test_update_task_rejects_status(
    client: AsyncClient, session_factory: SessionFactory, task: dict[str, Any]
) -> None:
    before = await backdate_task(client, session_factory, task["id"])

    response = await client.patch(f"/tasks/{task['id']}", json={"status": "done"})

    assert response.status_code == 422
    assert await get_task(client, task["id"]) == before


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"title": "New title"}, id="valid-title"),
        pytest.param({}, id="empty"),
        pytest.param({"title": "ab"}, id="short-title"),
    ],
)
async def test_update_done_task_is_conflict(
    client: AsyncClient, done_task: dict[str, Any], body: dict[str, Any]
) -> None:
    response = await client.patch(f"/tasks/{done_task['id']}", json=body)

    assert response.status_code == 409
    assert await get_task(client, done_task["id"]) == done_task


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"priority": "urgent"}, id="bad-priority"),
        pytest.param({"title": "New title", "status": "todo"}, id="extra-field"),
    ],
)
async def test_update_done_task_with_malformed_body(
    client: AsyncClient, done_task: dict[str, Any], body: dict[str, Any]
) -> None:
    response = await client.patch(f"/tasks/{done_task['id']}", json=body)

    assert response.status_code == 422
    assert await get_task(client, done_task["id"]) == done_task


async def test_start_task(
    client: AsyncClient, session_factory: SessionFactory, task: dict[str, Any]
) -> None:
    before = await backdate_task(client, session_factory, task["id"])

    response = await client.post(
        f"/tasks/{task['id']}/status", json={"status": "in_progress"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert updated_at(response.json()) > updated_at(before)


@pytest.mark.parametrize("new_status", ["done", "todo"])
async def test_change_status_from_in_progress(
    client: AsyncClient, task: dict[str, Any], new_status: str
) -> None:
    await client.post(f"/tasks/{task['id']}/status", json={"status": "in_progress"})

    response = await client.post(
        f"/tasks/{task['id']}/status", json={"status": new_status}
    )

    assert response.status_code == 200
    assert response.json()["status"] == new_status


async def test_change_status_rejects_extra_field(
    client: AsyncClient, task: dict[str, Any]
) -> None:
    response = await client.post(
        f"/tasks/{task['id']}/status", json={"status": "in_progress", "title": "X"}
    )

    assert response.status_code == 422
    assert (await get_task(client, task["id"]))["status"] == "todo"


@pytest.mark.parametrize("new_status", ["done", "todo"])
async def test_forbidden_transition_from_todo(
    client: AsyncClient, task: dict[str, Any], new_status: str
) -> None:
    response = await client.post(
        f"/tasks/{task['id']}/status", json={"status": new_status}
    )

    assert response.status_code == 409
    assert (await get_task(client, task["id"]))["status"] == "todo"


@pytest.mark.parametrize("new_status", ["in_progress", "todo"])
async def test_forbidden_transition_from_done(
    client: AsyncClient, task: dict[str, Any], new_status: str
) -> None:
    for step in ("in_progress", "done"):
        await client.post(f"/tasks/{task['id']}/status", json={"status": step})

    response = await client.post(
        f"/tasks/{task['id']}/status", json={"status": new_status}
    )

    assert response.status_code == 409
    assert (await get_task(client, task["id"]))["status"] == "done"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"status": "archived"}, id="unknown"),
        pytest.param({}, id="missing"),
    ],
)
async def test_change_status_rejects_invalid_value(
    client: AsyncClient, task: dict[str, Any], body: dict[str, Any]
) -> None:
    response = await client.post(f"/tasks/{task['id']}/status", json=body)

    assert response.status_code == 422


async def set_created_at(
    session_factory: SessionFactory, task_id: str, created_at: datetime
) -> None:
    async with session_factory() as session:
        await session.execute(
            update(TaskModel)
            .where(TaskModel.id == uuid.UUID(task_id))
            .values(created_at=created_at)
        )
        await session.commit()


async def list_tasks(
    client: AsyncClient, project_id: str, **params: Any
) -> dict[str, Any]:
    response = await client.get(f"/projects/{project_id}/tasks", params=params)
    assert response.status_code == 200
    return response.json()


def titles(page: dict[str, Any]) -> list[str]:
    return [item["title"] for item in page["items"]]


async def create_dated_tasks(
    client: AsyncClient,
    session_factory: SessionFactory,
    project_id: str,
    names: list[str],
) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for minutes, name in enumerate(names):
        created = await create_task(client, project_id, name)
        await set_created_at(
            session_factory, created["id"], base + timedelta(minutes=minutes)
        )


async def test_list_project_tasks(client: AsyncClient) -> None:
    project_a = await create_project(client, "Alpha")
    project_b = await create_project(client, "Beta")
    created = [
        await create_task(client, project_a, name)
        for name in ("Write spec", "Write tests", "Review spec")
    ]
    await create_task(client, project_b, "Foreign task")

    page = await list_tasks(client, project_a)

    assert page["total"] == 3
    assert page["limit"] == 20
    assert page["offset"] == 0
    by_id = {item["id"]: item for item in page["items"]}
    assert by_id == {task["id"]: task for task in created}


async def test_list_tasks_of_empty_project(
    client: AsyncClient, project_id: str
) -> None:
    page = await list_tasks(client, project_id)

    assert page == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_list_tasks_newest_first(
    client: AsyncClient, session_factory: SessionFactory, project_id: str
) -> None:
    await create_dated_tasks(
        client, session_factory, project_id, ["First", "Second", "Third"]
    )

    page = await list_tasks(client, project_id)

    assert titles(page) == ["Third", "Second", "First"]


async def test_list_tasks_order_is_stable_for_equal_created_at(
    client: AsyncClient, session_factory: SessionFactory, project_id: str
) -> None:
    same_time = datetime(2026, 1, 1, tzinfo=UTC)
    names = [f"Task {number}" for number in range(5)]
    for name in names:
        created = await create_task(client, project_id, name)
        await set_created_at(session_factory, created["id"], same_time)

    pages = [
        titles(await list_tasks(client, project_id, limit=2, offset=offset))
        for offset in (0, 2, 4)
    ]
    repeated = [
        titles(await list_tasks(client, project_id, limit=2, offset=offset))
        for offset in (0, 2, 4)
    ]

    assert sorted(name for page in pages for name in page) == sorted(names)
    assert repeated == pages


async def test_list_tasks_filtered_by_status(
    client: AsyncClient, project_id: str, insert_task: InsertTask
) -> None:
    project = uuid.UUID(project_id)
    await insert_task(project, "Todo task", TaskStatus.TO_DO)
    await insert_task(project, "Active task", TaskStatus.IN_PROGRESS)
    await insert_task(project, "Other active", TaskStatus.IN_PROGRESS)
    await insert_task(project, "Done task", TaskStatus.DONE)

    page = await list_tasks(client, project_id, status="in_progress")

    assert sorted(titles(page)) == ["Active task", "Other active"]
    assert {item["status"] for item in page["items"]} == {"in_progress"}
    assert page["total"] == 2


async def test_list_tasks_filtered_by_priority(
    client: AsyncClient, project_id: str
) -> None:
    await create_task(client, project_id, "Low task", priority="low")
    await create_task(client, project_id, "Medium task", priority="medium")
    await create_task(client, project_id, "High task", priority="high")

    page = await list_tasks(client, project_id, priority="high")

    assert titles(page) == ["High task"]
    assert page["items"][0]["priority"] == "high"
    assert page["total"] == 1


async def test_list_tasks_filtered_by_status_and_priority(
    client: AsyncClient, project_id: str
) -> None:
    await create_task(client, project_id, "High todo", priority="high")
    active = await create_task(client, project_id, "High active", priority="high")
    await client.post(f"/tasks/{active['id']}/status", json={"status": "in_progress"})
    await create_task(client, project_id, "Low todo", priority="low")

    page = await list_tasks(client, project_id, status="todo", priority="high")

    assert titles(page) == ["High todo"]
    assert page["total"] == 1


@pytest.mark.parametrize("params", [{"status": "archived"}, {"priority": "urgent"}])
async def test_list_tasks_with_invalid_filter(
    client: AsyncClient, project_id: str, params: dict[str, str]
) -> None:
    response = await client.get(f"/projects/{project_id}/tasks", params=params)

    assert response.status_code == 422


async def test_list_tasks_page(
    client: AsyncClient, session_factory: SessionFactory, project_id: str
) -> None:
    await create_dated_tasks(
        client, session_factory, project_id, ["One", "Two", "Three", "Four", "Five"]
    )

    page = await list_tasks(client, project_id, limit=2, offset=2)

    assert titles(page) == ["Three", "Two"]
    assert page["total"] == 5
    assert page["limit"] == 2
    assert page["offset"] == 2


async def test_list_tasks_offset_beyond_end(
    client: AsyncClient, project_id: str
) -> None:
    for name in ("Write spec", "Write tests", "Review spec"):
        await create_task(client, project_id, name)

    page = await list_tasks(client, project_id, offset=10)

    assert page["items"] == []
    assert page["total"] == 3


@pytest.mark.parametrize("limit", [1, 100])
async def test_list_tasks_limit_boundaries(
    client: AsyncClient, project_id: str, limit: int
) -> None:
    await create_task(client, project_id)

    page = await list_tasks(client, project_id, limit=limit)

    assert page["limit"] == limit
    assert len(page["items"]) == 1


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"limit": "abc"}, {"offset": -1}],
)
async def test_list_tasks_with_invalid_pagination(
    client: AsyncClient, project_id: str, params: dict[str, Any]
) -> None:
    response = await client.get(f"/projects/{project_id}/tasks", params=params)

    assert response.status_code == 422


async def test_list_tasks_of_unknown_project(client: AsyncClient) -> None:
    response = await client.get(f"/projects/{uuid.uuid4()}/tasks")

    assert response.status_code == 404


async def test_list_tasks_with_invalid_project_id(client: AsyncClient) -> None:
    response = await client.get("/projects/not-a-uuid/tasks")

    assert response.status_code == 422
