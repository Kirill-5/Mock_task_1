import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Project, Task, TaskPriority, TaskStatus
from app.domain.errors import TaskTitleAlreadyExists
from app.infrastructure.db.models import ProjectModel, TaskModel
from app.infrastructure.uow import SqlAlchemyUnitOfWork


@pytest.fixture
def uow(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)


async def save_project(uow: SqlAlchemyUnitOfWork, name: str = "Alpha") -> Project:
    project = Project.new(name)
    async with uow:
        await uow.projects.add(project)
        await uow.commit()
    return project


async def save_task(
    uow: SqlAlchemyUnitOfWork, project_id: uuid.UUID, title: str = "Write spec"
) -> Task:
    task = Task.new(project_id, title)
    async with uow:
        await uow.tasks.add(task)
        await uow.commit()
    return task


async def test_add_and_get_return_equal_task(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)
    task = await save_task(uow, project.id)

    async with uow:
        loaded = await uow.tasks.get(task.id)

    assert loaded == task


async def test_get_unknown_task_returns_none(uow: SqlAlchemyUnitOfWork) -> None:
    async with uow:
        assert await uow.tasks.get(uuid.uuid4()) is None


async def test_exists_by_title_ignores_case(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)
    await save_task(uow, project.id, "Write spec")

    async with uow:
        assert await uow.tasks.exists_by_title(project.id, "WRITE SPEC")
        assert await uow.tasks.exists_by_title(project.id, "write spec")
        assert not await uow.tasks.exists_by_title(project.id, "Review spec")


async def test_exists_by_title_ignores_other_projects(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    project = await save_project(uow, "Alpha")
    other = await save_project(uow, "Beta")
    await save_task(uow, other.id, "Write spec")

    async with uow:
        assert not await uow.tasks.exists_by_title(project.id, "Write spec")


async def test_update_persists_changes(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)
    task = await save_task(uow, project.id)
    task.update("Write tests", TaskPriority.HIGH)
    task.change_status(TaskStatus.IN_PROGRESS)

    async with uow:
        await uow.tasks.update(task)
        await uow.commit()

    async with uow:
        loaded = await uow.tasks.get(task.id)

    assert loaded == task


async def test_add_with_taken_title_raises_domain_error(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    project = await save_project(uow)
    await save_task(uow, project.id, "Write spec")

    async with uow:
        with pytest.raises(TaskTitleAlreadyExists):
            await uow.tasks.add(Task.new(project.id, "WRITE SPEC"))


async def test_update_to_taken_title_raises_domain_error(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    project = await save_project(uow)
    await save_task(uow, project.id, "Write spec")
    task = await save_task(uow, project.id, "Review spec")
    task.update("write spec")

    async with uow:
        with pytest.raises(TaskTitleAlreadyExists):
            await uow.tasks.update(task)


async def test_storage_rejects_titles_differing_only_in_case(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project = Project.new("Alpha")
    async with session_factory() as session:
        session.add(ProjectModel.from_domain(project))
        session.add(TaskModel.from_domain(Task.new(project.id, "Write spec")))
        await session.commit()

        session.add(TaskModel.from_domain(Task.new(project.id, "write spec")))
        with pytest.raises(IntegrityError, match="ux_tasks_project_id_title_lower"):
            await session.commit()
