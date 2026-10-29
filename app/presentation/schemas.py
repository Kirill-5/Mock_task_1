import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.entities import TaskPriority, TaskStatus


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    priority: TaskPriority = TaskPriority.MEDIUM


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    priority: TaskPriority | None = None


class TaskStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TaskStatus


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
