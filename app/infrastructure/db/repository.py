import uuid

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Project, TaskStatus
from app.domain.errors import ProjectNameAlreadyExists
from app.infrastructure.db.models import (
    PROJECT_NAME_UNIQUE_INDEX,
    ProjectModel,
    TaskModel,
)


def _violated_constraint(error: IntegrityError) -> str | None:
    return getattr(error.orig.__cause__, "constraint_name", None)


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

    async def has_tasks_in_progress(self, project_id: uuid.UUID) -> bool:
        query = select(
            exists().where(
                TaskModel.project_id == project_id,
                TaskModel.status == TaskStatus.IN_PROGRESS.value,
            )
        )
        return bool(await self._session.scalar(query))
