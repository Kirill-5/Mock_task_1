import json
import uuid
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models import ProjectModel

TOOL_NAMES = {
    "create_project",
    "get_project",
    "delete_project",
    "create_task",
    "get_task",
    "list_tasks",
    "update_task",
    "change_task_status",
}


async def call(client: Client, tool: str, **arguments: Any) -> dict[str, Any]:
    result = await client.call_tool(tool, arguments)
    return result.structured_content


async def create_project(client: Client, name: str = "Alpha") -> dict[str, Any]:
    return await call(client, "create_project", name=name)


async def create_task(
    client: Client, project_id: str, title: str = "Write spec", **arguments: Any
) -> dict[str, Any]:
    return await call(
        client, "create_task", project_id=project_id, title=title, **arguments
    )


async def count_projects(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(ProjectModel))


@pytest.fixture
async def project(mcp_client: Client) -> dict[str, Any]:
    return await create_project(mcp_client)


@pytest.fixture
async def task(mcp_client: Client, project: dict[str, Any]) -> dict[str, Any]:
    return await create_task(mcp_client, project["id"])


async def test_list_tools(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()

    assert {tool.name for tool in tools} == TOOL_NAMES
    for tool in tools:
        assert tool.description
        assert tool.input_schema["properties"]


async def test_tool_behavior_hints(mcp_client: Client) -> None:
    tools = {tool.name: tool.annotations for tool in await mcp_client.list_tools()}

    for name in ("get_project", "get_task", "list_tasks"):
        assert tools[name].read_only_hint is True
    assert tools["delete_project"].destructive_hint is True


async def test_create_and_get_project(mcp_client: Client) -> None:
    created = await create_project(mcp_client, "  Alpha  ")
    loaded = await call(mcp_client, "get_project", project_id=created["id"])

    assert created["name"] == "Alpha"
    assert loaded == created


async def test_create_project_with_taken_name(
    mcp_client: Client,
    project: dict[str, Any],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(ToolError, match="^conflict:"):
        await create_project(mcp_client, "alpha")

    assert await count_projects(session_factory) == 1


async def test_delete_project(mcp_client: Client, project: dict[str, Any]) -> None:
    result = await call(mcp_client, "delete_project", project_id=project["id"])

    assert result == {"deleted": project["id"]}
    with pytest.raises(ToolError, match="^not_found:"):
        await call(mcp_client, "get_project", project_id=project["id"])


async def test_delete_project_with_task_in_progress(
    mcp_client: Client, project: dict[str, Any], task: dict[str, Any]
) -> None:
    await call(
        mcp_client, "change_task_status", task_id=task["id"], status="in_progress"
    )

    with pytest.raises(ToolError, match="^conflict:"):
        await call(mcp_client, "delete_project", project_id=project["id"])

    assert await call(mcp_client, "get_project", project_id=project["id"]) == project


async def test_task_lifecycle(mcp_client: Client, project: dict[str, Any]) -> None:
    task = await create_task(mcp_client, project["id"], priority="high")
    await call(mcp_client, "update_task", task_id=task["id"], title="Write tests")
    await call(
        mcp_client, "change_task_status", task_id=task["id"], status="in_progress"
    )
    await call(mcp_client, "change_task_status", task_id=task["id"], status="done")

    loaded = await call(mcp_client, "get_task", task_id=task["id"])

    assert loaded["title"] == "Write tests"
    assert loaded["priority"] == "high"
    assert loaded["status"] == "done"


async def test_forbidden_status_transition(
    mcp_client: Client, task: dict[str, Any]
) -> None:
    with pytest.raises(ToolError, match="^conflict:"):
        await call(mcp_client, "change_task_status", task_id=task["id"], status="done")

    loaded = await call(mcp_client, "get_task", task_id=task["id"])
    assert loaded["status"] == "todo"


async def test_update_done_task(mcp_client: Client, task: dict[str, Any]) -> None:
    await call(
        mcp_client, "change_task_status", task_id=task["id"], status="in_progress"
    )
    done = await call(
        mcp_client, "change_task_status", task_id=task["id"], status="done"
    )

    with pytest.raises(ToolError, match="^conflict:"):
        await call(mcp_client, "update_task", task_id=task["id"], title="New title")

    assert await call(mcp_client, "get_task", task_id=task["id"]) == done


async def test_create_task_in_unknown_project(mcp_client: Client) -> None:
    with pytest.raises(ToolError, match="^not_found:"):
        await create_task(mcp_client, str(uuid.uuid4()))


async def test_list_tasks_with_filter_and_pagination(
    mcp_client: Client, project: dict[str, Any]
) -> None:
    for title in ("High one", "High two", "High three"):
        await create_task(mcp_client, project["id"], title, priority="high")
    await create_task(mcp_client, project["id"], "Low one", priority="low")

    page = await call(
        mcp_client, "list_tasks", project_id=project["id"], priority="high", limit=2
    )

    assert len(page["items"]) == 2
    assert {item["priority"] for item in page["items"]} == {"high"}
    assert page["total"] == 3
    assert page["limit"] == 2
    assert page["offset"] == 0


@pytest.mark.parametrize("limit", [0, 101])
async def test_list_tasks_with_invalid_limit(
    mcp_client: Client, project: dict[str, Any], limit: int
) -> None:
    with pytest.raises(ToolError):
        await call(mcp_client, "list_tasks", project_id=project["id"], limit=limit)


async def test_domain_validation_error(
    mcp_client: Client, project: dict[str, Any]
) -> None:
    with pytest.raises(ToolError, match="^validation:"):
        await create_task(mcp_client, project["id"], "ab")


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_task", {"task_id": "not-a-uuid"}),
        ("change_task_status", {"task_id": str(uuid.uuid4()), "status": "archived"}),
    ],
)
async def test_invalid_arguments(
    mcp_client: Client, tool: str, arguments: dict[str, Any]
) -> None:
    with pytest.raises(ToolError):
        await mcp_client.call_tool(tool, arguments)


async def test_server_keeps_working_after_error(mcp_client: Client) -> None:
    with pytest.raises(ToolError, match="^not_found:"):
        await call(mcp_client, "get_project", project_id=str(uuid.uuid4()))

    project = await create_project(mcp_client)

    assert project["name"] == "Alpha"


async def test_read_project_resource(
    mcp_client: Client, project: dict[str, Any]
) -> None:
    await create_task(mcp_client, project["id"], "Write spec")
    await create_task(mcp_client, project["id"], "Write tests")

    contents = await mcp_client.read_resource(f"project://{project['id']}")
    data = json.loads(contents[0].text)

    assert data["project"] == project
    assert len(data["tasks"]) == 2
    assert data["total"] == 2


async def test_read_unknown_project_resource(mcp_client: Client) -> None:
    with pytest.raises(MCPError, match="not_found:"):
        await mcp_client.read_resource(f"project://{uuid.uuid4()}")
