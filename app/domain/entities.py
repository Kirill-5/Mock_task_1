import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.domain.errors import (
    DomainValidationError,
    InvalidStatusTransition,
    TaskAlreadyDone,
)

MAX_PROJECT_NAME_LENGTH = 100
MIN_PROJECT_NAME_LENGTH = 3
MAX_PROJECT_DESCRIPTION_LENGTH = 1000
MIN_TASK_TITLE_LENGTH = 3
MAX_TASK_TITLE_LENGTH = 200


class TaskStatus(StrEnum):
    TO_DO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


ALLOWED_STATUS_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.TO_DO: frozenset({TaskStatus.IN_PROGRESS}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.DONE, TaskStatus.TO_DO}),
    TaskStatus.DONE: frozenset(),
}


def _normalize_title(title: str) -> str:
    title = title.strip()
    if not (MIN_TASK_TITLE_LENGTH <= len(title) <= MAX_TASK_TITLE_LENGTH):
        raise DomainValidationError(
            f"title must be between {MIN_TASK_TITLE_LENGTH} "
            f"and {MAX_TASK_TITLE_LENGTH} characters"
        )
    return title


def _validate_priority(priority: TaskPriority | str) -> TaskPriority:
    try:
        return TaskPriority(priority)
    except ValueError:
        raise DomainValidationError(
            f"priority must be one of: {', '.join(TaskPriority)}"
        ) from None


@dataclass(frozen=True)
class Project:
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime

    @classmethod
    def new(cls, name: str, description: str | None = None) -> "Project":
        name = name.strip()
        description = (description.strip() or None) if description else None

        if not (MIN_PROJECT_NAME_LENGTH <= len(name) <= MAX_PROJECT_NAME_LENGTH):
            raise DomainValidationError(
                f"name must be between {MIN_PROJECT_NAME_LENGTH} "
                f"and {MAX_PROJECT_NAME_LENGTH} characters"
            )

        if (
            description is not None
            and len(description) > MAX_PROJECT_DESCRIPTION_LENGTH
        ):
            raise DomainValidationError(
                f"description must not exceed {MAX_PROJECT_DESCRIPTION_LENGTH} characters"
            )

        return cls(
            id=uuid.uuid4(),
            name=name,
            description=description,
            created_at=datetime.now(UTC),
        )


@dataclass
class Task:
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        project_id: uuid.UUID,
        title: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
    ) -> "Task":
        title = _normalize_title(title)
        priority = _validate_priority(priority)
        current_time = datetime.now(UTC)

        return cls(
            id=uuid.uuid4(),
            project_id=project_id,
            title=title,
            priority=priority,
            status=TaskStatus.TO_DO,
            created_at=current_time,
            updated_at=current_time,
        )

    def change_status(self, new_status: TaskStatus) -> None:
        allowed = ALLOWED_STATUS_TRANSITIONS[self.status]

        if new_status not in allowed:
            raise InvalidStatusTransition(
                f"cannot change status from {self.status} to {new_status}"
            )

        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def update(
        self,
        new_title: str | None = None,
        new_priority: TaskPriority | None = None,
    ) -> None:
        if self.status == TaskStatus.DONE:
            raise TaskAlreadyDone(f"task {self.id} is done and cannot be changed")

        if new_title is None and new_priority is None:
            raise DomainValidationError("title or priority must be provided")

        if new_title is not None:
            new_title = _normalize_title(new_title)

        if new_priority is not None:
            new_priority = _validate_priority(new_priority)

        if new_title is not None:
            self.title = new_title
        if new_priority is not None:
            self.priority = new_priority

        self.updated_at = datetime.now(UTC)
