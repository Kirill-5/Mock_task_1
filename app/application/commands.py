import uuid
from dataclasses import dataclass

from app.domain.entities import TaskPriority, TaskStatus, Task


@dataclass(frozen=True)
class CreateProject:
    name: str
    description: str | None = None


@dataclass(frozen=True)
class DeleteProject:
    project_id: uuid.UUID


@dataclass(frozen=True)
class GetProject:
    project_id: uuid.UUID


@dataclass(frozen=True)
class ListProjectTasks:
    project_id: uuid.UUID
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    offset: int = 0
    limit: int = 20


@dataclass(frozen=True)
class CreateTask:
    project_id: uuid.UUID
    title: str
    priority: TaskPriority = TaskPriority.MEDIUM


@dataclass(frozen=True)
class GetTask:
    task_id: uuid.UUID


@dataclass(frozen=True)
class TaskPage:
    items: list[Task]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class UpdateTask:
    task_id: uuid.UUID
    title: str | None = None
    priority: TaskPriority | None = None


@dataclass(frozen=True)
class ChangeTaskStatus:
    task_id: uuid.UUID
    status: TaskStatus
