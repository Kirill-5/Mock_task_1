import uuid

import pytest

from app.domain.entities import Task, TaskStatus
from app.domain.errors import DomainValidationError, TaskAlreadyDone


def test_empty_update_is_rejected() -> None:
    task = Task.new(uuid.uuid4(), "Write spec")
    updated_at = task.updated_at

    with pytest.raises(DomainValidationError):
        task.update()

    assert task.updated_at == updated_at


def test_empty_update_of_done_task_is_conflict() -> None:
    task = Task.new(uuid.uuid4(), "Write spec")
    task.change_status(TaskStatus.IN_PROGRESS)
    task.change_status(TaskStatus.DONE)

    with pytest.raises(TaskAlreadyDone):
        task.update()
