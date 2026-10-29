import uuid

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Project, Task, TaskStatus
from app.domain.errors import ProjectNameAlreadyExists, TaskTitleAlreadyExists
from app.infrastructure.db.models import (
    PROJECT_NAME_UNIQUE_INDEX,
    TASK_TITLE_UNIQUE_INDEX,
    ProjectModel,
    TaskModel,
)


def _violated_constraint(error: IntegrityError) -> str | None:
    return getattr(error.orig.__cause__, "constraint_name", None)


def _raise_if_title_taken(error: IntegrityError, task: Task) -> None:
    if _violated_constraint(error) == TASK_TITLE_UNIQUE_INDEX:
        raise TaskTitleAlreadyExists(
            f"task with title '{task.title}' already exists in project {task.project_id}"
        ) from error


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: Project) -> None:
        self._session.add(ProjectModel.from_domain(project))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if _violated_constraint(error) == PROJECT_NAME_UNIQUE_INDEX:
                raise ProjectNameAlreadyExists(
                    f"project with name '{project.name}' already exists"
                ) from error
            raise

    async def get(self, project_id: uuid.UUID) -> Project | None:
        model = await self._session.get(ProjectModel, project_id)
        return model.to_domain() if model is not None else None

    async def delete(self, project: Project) -> None:
        await self._session.execute(
            delete(ProjectModel).where(ProjectModel.id == project.id)
        )
        await self._session.flush()

    async def exists_by_name(self, name: str) -> bool:
        query = select(
            exists().where(func.lower(ProjectModel.name) == func.lower(name))
        )
        return bool(await self._session.scalar(query))


class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: Task) -> None:
        self._session.add(TaskModel.from_domain(task))
        try:
            await self._session.flush()
        except IntegrityError as error:
            _raise_if_title_taken(error, task)
            raise

    async def get(self, task_id: uuid.UUID) -> Task | None:
        model = await self._session.get(TaskModel, task_id)
        return model.to_domain() if model is not None else None

    async def update(self, task: Task) -> None:
        statement = (
            update(TaskModel)
            .where(TaskModel.id == task.id)
            .values(
                title=task.title,
                priority=task.priority.value,
                status=task.status.value,
                updated_at=task.updated_at,
            )
        )
        try:
            await self._session.execute(statement)
            await self._session.flush()
        except IntegrityError as error:
            _raise_if_title_taken(error, task)
            raise

    async def exists_by_title(self, project_id: uuid.UUID, title: str) -> bool:
        query = select(
            exists().where(
                TaskModel.project_id == project_id,
                func.lower(TaskModel.title) == func.lower(title),
            )
        )
        return bool(await self._session.scalar(query))

    async def has_tasks_in_progress(self, project_id: uuid.UUID) -> bool:
        query = select(
            exists().where(
                TaskModel.project_id == project_id,
                TaskModel.status == TaskStatus.IN_PROGRESS.value,
            )
        )
        return bool(await self._session.scalar(query))
