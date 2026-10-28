import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.entities import (
    MAX_PROJECT_DESCRIPTION_LENGTH,
    MAX_PROJECT_NAME_LENGTH,
    MAX_TASK_TITLE_LENGTH,
    Project,
    Task,
    TaskPriority,
    TaskStatus,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

PROJECT_NAME_UNIQUE_INDEX = "ux_projects_name_lower"
TASK_TITLE_UNIQUE_INDEX = "ux_tasks_project_id_title_lower"


def _in_values(column: str, values: type[TaskStatus] | type[TaskPriority]) -> str:
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({allowed})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(MAX_PROJECT_NAME_LENGTH))
    description: Mapped[str | None] = mapped_column(
        String(MAX_PROJECT_DESCRIPTION_LENGTH)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @classmethod
    def from_domain(cls, project: Project) -> "ProjectModel":
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
        )

    def to_domain(self) -> Project:
        return Project(
            id=self.id,
            name=self.name,
            description=self.description,
            created_at=self.created_at,
        )


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_project_id_created_at", "project_id", "created_at"),
        CheckConstraint(_in_values("status", TaskStatus), name="status"),
        CheckConstraint(_in_values("priority", TaskPriority), name="priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(MAX_TASK_TITLE_LENGTH))
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @classmethod
    def from_domain(cls, task: Task) -> "TaskModel":
        return cls(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            priority=task.priority.value,
            status=task.status.value,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    def to_domain(self) -> Task:
        return Task(
            id=self.id,
            project_id=self.project_id,
            title=self.title,
            priority=TaskPriority(self.priority),
            status=TaskStatus(self.status),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


Index(PROJECT_NAME_UNIQUE_INDEX, func.lower(ProjectModel.name), unique=True)
Index(
    TASK_TITLE_UNIQUE_INDEX,
    TaskModel.project_id,
    func.lower(TaskModel.title),
    unique=True,
)
