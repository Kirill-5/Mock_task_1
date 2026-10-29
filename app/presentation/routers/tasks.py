import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.commands import ChangeTaskStatus, CreateTask, GetTask, UpdateTask
from app.application.use_cases import (
    ChangeTaskStatusUseCase,
    CreateTaskUseCase,
    GetTaskUseCase,
    UpdateTaskUseCase,
)
from app.presentation.deps import (
    get_change_task_status_use_case,
    get_create_task_use_case,
    get_get_task_use_case,
    get_update_task_use_case,
)
from app.presentation.schemas import TaskCreate, TaskRead, TaskStatusChange, TaskUpdate

router = APIRouter(tags=["tasks"])


@router.post(
    "/projects/{project_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskRead,
)
async def create_task(
    project_id: uuid.UUID,
    body: TaskCreate,
    use_case: Annotated[CreateTaskUseCase, Depends(get_create_task_use_case)],
) -> TaskRead:
    task = await use_case.execute(
        CreateTask(project_id=project_id, title=body.title, priority=body.priority)
    )
    return TaskRead.model_validate(task)


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    use_case: Annotated[GetTaskUseCase, Depends(get_get_task_use_case)],
) -> TaskRead:
    task = await use_case.execute(GetTask(task_id=task_id))
    return TaskRead.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    use_case: Annotated[UpdateTaskUseCase, Depends(get_update_task_use_case)],
) -> TaskRead:
    task = await use_case.execute(
        UpdateTask(task_id=task_id, title=body.title, priority=body.priority)
    )
    return TaskRead.model_validate(task)


@router.post("/tasks/{task_id}/status", response_model=TaskRead)
async def change_task_status(
    task_id: uuid.UUID,
    body: TaskStatusChange,
    use_case: Annotated[
        ChangeTaskStatusUseCase, Depends(get_change_task_status_use_case)
    ],
) -> TaskRead:
    task = await use_case.execute(ChangeTaskStatus(task_id=task_id, status=body.status))
    return TaskRead.model_validate(task)
