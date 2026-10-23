import uuid
from types import TracebackType
from typing import Protocol, Self

from app.domain.entities import Project, Task, TaskPriority, TaskStatus


class ProjectRepository(Protocol):
    async def add(self, project: Project) -> None: ...

    async def get(self, project_id: uuid.UUID) -> Project | None: ...

    async def delete(self, project: Project) -> None: ...

    async def exists_by_name(self, name: str) -> bool: ...


class TaskRepository(Protocol):
    async def add(self, task: Task) -> None: ...

    async def get(self, task_id: uuid.UUID) -> Task | None: ...

    async def update(self, task: Task) -> None: ...

    async def exists_by_title(self, project_id: uuid.UUID, title: str) -> bool: ...

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Task]: ...

    async def count_by_project(
        self,
        project_id: uuid.UUID,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> int: ...

    async def has_tasks_in_progress(self, project_id: uuid.UUID) -> bool: ...


class UnitOfWork(Protocol):
    projects: ProjectRepository
    tasks: TaskRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...