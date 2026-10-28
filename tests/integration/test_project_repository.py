import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Project, Task, TaskStatus
from app.domain.errors import ProjectNameAlreadyExists
from app.infrastructure.db.models import ProjectModel
from app.infrastructure.uow import SqlAlchemyUnitOfWork

InsertTask = Callable[..., Awaitable[Task]]


@pytest.fixture
def uow(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)


async def save_project(uow: SqlAlchemyUnitOfWork, name: str = "Alpha") -> Project:
    project = Project.new(name, "Описание")
    async with uow:
        await uow.projects.add(project)
        await uow.commit()
    return project


async def test_add_and_get_return_equal_project(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)

    async with uow:
        loaded = await uow.projects.get(project.id)

    assert loaded == project


async def test_get_unknown_project_returns_none(uow: SqlAlchemyUnitOfWork) -> None:
    async with uow:
        assert await uow.projects.get(uuid.uuid4()) is None


async def test_exists_by_name_ignores_case(uow: SqlAlchemyUnitOfWork) -> None:
    await save_project(uow, "Alpha")

    async with uow:
        assert await uow.projects.exists_by_name("ALPHA")
        assert await uow.projects.exists_by_name("alpha")
        assert not await uow.projects.exists_by_name("Beta")


async def test_delete_removes_project(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)

    async with uow:
        await uow.projects.delete(project)
        await uow.commit()

    async with uow:
        assert await uow.projects.get(project.id) is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TaskStatus.TO_DO, False),
        (TaskStatus.IN_PROGRESS, True),
        (TaskStatus.DONE, False),
    ],
)
async def test_has_tasks_in_progress(
    uow: SqlAlchemyUnitOfWork,
    insert_task: InsertTask,
    status: TaskStatus,
    expected: bool,
) -> None:
    project = await save_project(uow)
    await insert_task(project.id, status=status)

    async with uow:
        assert await uow.tasks.has_tasks_in_progress(project.id) is expected


async def test_has_tasks_in_progress_ignores_other_projects(
    uow: SqlAlchemyUnitOfWork, insert_task: InsertTask
) -> None:
    project = await save_project(uow, "Alpha")
    other = await save_project(uow, "Beta")
    await insert_task(other.id, status=TaskStatus.IN_PROGRESS)

    async with uow:
        assert not await uow.tasks.has_tasks_in_progress(project.id)


async def test_changes_without_commit_are_not_visible(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project = Project.new("Alpha")

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.projects.add(project)
        async with SqlAlchemyUnitOfWork(session_factory) as other_uow:
            assert await other_uow.projects.get(project.id) is None

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.projects.get(project.id) is None


async def test_storage_rejects_names_differing_only_in_case(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(ProjectModel.from_domain(Project.new("Alpha")))
        await session.commit()

        session.add(ProjectModel.from_domain(Project.new("alpha")))
        with pytest.raises(IntegrityError, match="ux_projects_name_lower"):
            await session.commit()


async def test_add_with_taken_name_raises_domain_error(
    uow: SqlAlchemyUnitOfWork,
) -> None:
    await save_project(uow, "Alpha")

    async with uow:
        with pytest.raises(ProjectNameAlreadyExists):
            await uow.projects.add(Project.new("ALPHA"))
