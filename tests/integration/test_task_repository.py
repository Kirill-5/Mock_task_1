import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
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
    uow: SqlAlchemyUnitOfWork,
    project_id: uuid.UUID,
    title: str = "Write spec",
    priority: TaskPriority = TaskPriority.MEDIUM,
    status: TaskStatus = TaskStatus.TO_DO,
) -> Task:
    task = Task.new(project_id, title, priority)
    if status is not TaskStatus.TO_DO:
        task.change_status(TaskStatus.IN_PROGRESS)
    if status is TaskStatus.DONE:
        task.change_status(TaskStatus.DONE)
    async with uow:
        await uow.tasks.add(task)
        await uow.commit()
    return task


async def set_created_at(
    session_factory: async_sessionmaker[AsyncSession],
    task: Task,
    created_at: datetime,
) -> None:
    async with session_factory() as session:
        await session.execute(
            update(TaskModel)
            .where(TaskModel.id == task.id)
            .values(created_at=created_at)
        )
        await session.commit()


async def list_titles(
    uow: SqlAlchemyUnitOfWork, project_id: uuid.UUID, **filters: object
) -> list[str]:
    async with uow:
        tasks = await uow.tasks.list_by_project(project_id, **filters)
    return [task.title for task in tasks]


async def count(
    uow: SqlAlchemyUnitOfWork, project_id: uuid.UUID, **filters: object
) -> int:
    async with uow:
        return await uow.tasks.count_by_project(project_id, **filters)


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


async def test_list_returns_only_tasks_of_project(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow, "Alpha")
    other = await save_project(uow, "Beta")
    await save_task(uow, project.id, "Write spec")
    await save_task(uow, project.id, "Review spec")
    await save_task(uow, other.id, "Foreign task")

    assert sorted(await list_titles(uow, project.id)) == ["Review spec", "Write spec"]
    assert await count(uow, project.id) == 2


async def test_list_and_count_filter_by_status(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)
    await save_task(uow, project.id, "Todo task")
    await save_task(uow, project.id, "Active task", status=TaskStatus.IN_PROGRESS)
    await save_task(uow, project.id, "Done task", status=TaskStatus.DONE)

    filters = {"status": TaskStatus.IN_PROGRESS}
    assert await list_titles(uow, project.id, **filters) == ["Active task"]
    assert await count(uow, project.id, **filters) == 1


async def test_list_and_count_filter_by_priority(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)
    await save_task(uow, project.id, "Low task", TaskPriority.LOW)
    await save_task(uow, project.id, "High task", TaskPriority.HIGH)
    await save_task(uow, project.id, "Other high", TaskPriority.HIGH)

    filters = {"priority": TaskPriority.HIGH}
    titles = await list_titles(uow, project.id, **filters)
    assert sorted(titles) == ["High task", "Other high"]
    assert await count(uow, project.id, **filters) == 2


async def test_list_and_count_combine_filters(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)
    await save_task(uow, project.id, "High todo", TaskPriority.HIGH)
    await save_task(
        uow,
        project.id,
        "High active",
        TaskPriority.HIGH,
        TaskStatus.IN_PROGRESS,
    )
    await save_task(uow, project.id, "Low todo", TaskPriority.LOW)

    filters = {"status": TaskStatus.TO_DO, "priority": TaskPriority.HIGH}
    assert await list_titles(uow, project.id, **filters) == ["High todo"]
    assert await count(uow, project.id, **filters) == 1


async def test_list_orders_newest_first(
    uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project = await save_project(uow)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for minutes, title in enumerate(["First", "Second", "Third"]):
        task = await save_task(uow, project.id, title)
        await set_created_at(session_factory, task, base + timedelta(minutes=minutes))

    assert await list_titles(uow, project.id) == ["Third", "Second", "First"]


async def test_list_order_is_stable_for_equal_created_at(
    uow: SqlAlchemyUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project = await save_project(uow)
    same_time = datetime(2026, 1, 1, tzinfo=UTC)
    titles = {f"Task {number}" for number in range(5)}
    for title in titles:
        task = await save_task(uow, project.id, title)
        await set_created_at(session_factory, task, same_time)

    pages = [
        await list_titles(uow, project.id, limit=2, offset=offset)
        for offset in (0, 2, 4)
    ]
    repeated = [
        await list_titles(uow, project.id, limit=2, offset=offset)
        for offset in (0, 2, 4)
    ]

    flat = [title for page in pages for title in page]
    assert sorted(flat) == sorted(titles)
    assert repeated == pages


async def test_list_offset_beyond_end_returns_empty(uow: SqlAlchemyUnitOfWork) -> None:
    project = await save_project(uow)
    await save_task(uow, project.id)

    assert await list_titles(uow, project.id, offset=10) == []
    assert await count(uow, project.id) == 1
