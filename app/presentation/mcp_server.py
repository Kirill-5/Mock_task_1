import uuid
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ResourceError, ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from app.application.commands import (
    ChangeTaskStatus,
    CreateProject,
    CreateTask,
    DeleteProject,
    GetProject,
    GetTask,
    ListProjectTasks,
    UpdateTask,
)
from app.application.ports import UowFactory
from app.application.use_cases import (
    ChangeTaskStatusUseCase,
    CreateProjectUseCase,
    CreateTaskUseCase,
    DeleteProjectUseCase,
    GetProjectUseCase,
    GetTaskUseCase,
    ListProjectTasksUseCase,
    UpdateTaskUseCase,
)
from app.domain.entities import TaskPriority, TaskStatus
from app.domain.errors import (
    ConflictError,
    DomainError,
    DomainValidationError,
    NotFoundError,
)
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.settings import Settings
from app.infrastructure.uow import SqlAlchemyUnitOfWork
from app.presentation.schemas import ProjectRead, TaskPageRead, TaskRead

ERROR_CATEGORIES: dict[type[DomainError], str] = {
    NotFoundError: "not_found",
    ConflictError: "conflict",
    DomainValidationError: "validation",
}

RESOURCE_TASKS_LIMIT = 100

READ_ONLY = ToolAnnotations(readOnlyHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

ProjectId = Annotated[
    uuid.UUID, Field(description="Project id taken from a previous tool result.")
]
TaskId = Annotated[
    uuid.UUID, Field(description="Task id taken from a previous tool result.")
]


def _describe(error: DomainError) -> str:
    for error_class, category in ERROR_CATEGORIES.items():
        if isinstance(error, error_class):
            return f"{category}: {error}"
    return f"error: {error}"


async def _run_tool[T](call: Awaitable[T]) -> T:
    try:
        return await call
    except DomainError as error:
        raise ToolError(_describe(error)) from error


def _uow_factory(ctx: Context) -> UowFactory:
    return ctx.lifespan_context


def create_mcp(settings: Settings | None = None) -> FastMCP:
    mcp_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[UowFactory]:
        engine = create_engine(mcp_settings.database_url)
        session_factory = create_session_factory(engine)
        yield lambda: SqlAlchemyUnitOfWork(session_factory)
        await engine.dispose()

    mcp = FastMCP(
        "projects-and-tasks",
        instructions=(
            "Manage projects and their tasks. Always take project and task ids "
            "from previous tool results, never invent them. Errors start with "
            "a category: not_found, conflict or validation."
        ),
        lifespan=lifespan,
        mask_error_details=True,
    )

    @mcp.tool(annotations=WRITE)
    async def create_project(
        name: str, ctx: Context, description: str | None = None
    ) -> ProjectRead:
        """Create a project.

        The name is trimmed, must be 3-100 characters and unique ignoring case.
        The description is optional, up to 1000 characters.
        Errors: conflict if the name is taken, validation if lengths are wrong.
        """
        use_case = CreateProjectUseCase(_uow_factory(ctx))
        project = await _run_tool(
            use_case.execute(CreateProject(name=name, description=description))
        )
        return ProjectRead.model_validate(project)

    @mcp.tool(annotations=READ_ONLY)
    async def get_project(project_id: ProjectId, ctx: Context) -> ProjectRead:
        """Get a project by id. Errors: not_found if there is no such project."""
        use_case = GetProjectUseCase(_uow_factory(ctx))
        project = await _run_tool(use_case.execute(GetProject(project_id=project_id)))
        return ProjectRead.model_validate(project)

    @mcp.tool(annotations=DESTRUCTIVE)
    async def delete_project(project_id: ProjectId, ctx: Context) -> dict[str, str]:
        """Delete a project together with all its tasks. Cannot be undone.

        Confirm with the user before calling.
        Errors: not_found if there is no such project, conflict if the project
        has tasks in progress.
        """
        use_case = DeleteProjectUseCase(_uow_factory(ctx))
        await _run_tool(use_case.execute(DeleteProject(project_id=project_id)))
        return {"deleted": str(project_id)}

    @mcp.tool(annotations=WRITE)
    async def create_task(
        project_id: ProjectId,
        title: str,
        ctx: Context,
        priority: TaskPriority = TaskPriority.MEDIUM,
    ) -> TaskRead:
        """Create a task in a project. New tasks always start in status todo.

        The title is trimmed, must be 3-200 characters and unique within the
        project ignoring case.
        Errors: not_found if there is no such project, conflict if the title is
        taken, validation if the title length is wrong.
        """
        use_case = CreateTaskUseCase(_uow_factory(ctx))
        task = await _run_tool(
            use_case.execute(
                CreateTask(project_id=project_id, title=title, priority=priority)
            )
        )
        return TaskRead.model_validate(task)

    @mcp.tool(annotations=READ_ONLY)
    async def get_task(task_id: TaskId, ctx: Context) -> TaskRead:
        """Get a task by id. Errors: not_found if there is no such task."""
        use_case = GetTaskUseCase(_uow_factory(ctx))
        task = await _run_tool(use_case.execute(GetTask(task_id=task_id)))
        return TaskRead.model_validate(task)

    @mcp.tool(annotations=READ_ONLY)
    async def list_tasks(
        project_id: ProjectId,
        ctx: Context,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> TaskPageRead:
        """List tasks of a project, newest first.

        Optional filters by status and priority. Use limit and offset to page
        through results; total is the number of tasks matching the filters.
        Errors: not_found if there is no such project.
        """
        use_case = ListProjectTasksUseCase(_uow_factory(ctx))
        page = await _run_tool(
            use_case.execute(
                ListProjectTasks(
                    project_id=project_id,
                    status=status,
                    priority=priority,
                    limit=limit,
                    offset=offset,
                )
            )
        )
        return TaskPageRead.model_validate(page)

    @mcp.tool(annotations=WRITE)
    async def update_task(
        task_id: TaskId,
        ctx: Context,
        title: str | None = None,
        priority: TaskPriority | None = None,
    ) -> TaskRead:
        """Change the title and/or priority of a task. Pass at least one of them.

        Status is changed only with change_task_status.
        Errors: not_found if there is no such task, conflict if the task is done
        or the title is taken, validation if nothing to change or the title
        length is wrong.
        """
        use_case = UpdateTaskUseCase(_uow_factory(ctx))
        task = await _run_tool(
            use_case.execute(
                UpdateTask(task_id=task_id, title=title, priority=priority)
            )
        )
        return TaskRead.model_validate(task)

    @mcp.tool(annotations=WRITE)
    async def change_task_status(
        task_id: TaskId, status: TaskStatus, ctx: Context
    ) -> TaskRead:
        """Change the status of a task.

        Allowed transitions: todo -> in_progress, in_progress -> done,
        in_progress -> todo. A done task cannot change.
        Errors: not_found if there is no such task, conflict if the transition
        is not allowed.
        """
        use_case = ChangeTaskStatusUseCase(_uow_factory(ctx))
        task = await _run_tool(
            use_case.execute(ChangeTaskStatus(task_id=task_id, status=status))
        )
        return TaskRead.model_validate(task)

    @mcp.resource(
        "project://{project_id}",
        mime_type="application/json",
        description=(
            f"A project with up to {RESOURCE_TASKS_LIMIT} of its tasks, newest "
            "first, and the total number of tasks."
        ),
    )
    async def project_resource(project_id: str, ctx: Context) -> dict[str, Any]:
        try:
            parsed_id = uuid.UUID(project_id)
        except ValueError as error:
            raise ResourceError(
                f"validation: invalid project id {project_id}"
            ) from error

        uow_factory = _uow_factory(ctx)
        try:
            project = await GetProjectUseCase(uow_factory).execute(
                GetProject(project_id=parsed_id)
            )
            page = await ListProjectTasksUseCase(uow_factory).execute(
                ListProjectTasks(project_id=parsed_id, limit=RESOURCE_TASKS_LIMIT)
            )
        except DomainError as error:
            raise ResourceError(_describe(error)) from error

        tasks = TaskPageRead.model_validate(page)
        return {
            "project": ProjectRead.model_validate(project).model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in tasks.items],
            "total": tasks.total,
        }

    return mcp


mcp = create_mcp()


if __name__ == "__main__":
    mcp.run()
