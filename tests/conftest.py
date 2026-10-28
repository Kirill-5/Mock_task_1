import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.entities import Task, TaskStatus
from app.infrastructure.db.models import TaskModel
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.settings import Settings
from app.main import create_app

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

STATUS_PATH: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.TO_DO: [],
    TaskStatus.IN_PROGRESS: [TaskStatus.IN_PROGRESS],
    TaskStatus.DONE: [TaskStatus.IN_PROGRESS, TaskStatus.DONE],
}

InsertTask = Callable[..., Awaitable[Task]]


@pytest.fixture(scope="session")
def settings() -> Settings:
    defaults = Settings()
    return Settings(database_url=defaults.test_database_url)


@pytest.fixture(scope="session")
def migrated_database(settings: Settings) -> None:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", settings.database_url)
    config.attributes["configure_logger"] = False
    try:
        command.upgrade(config, "head")
    except OSError as exc:
        pytest.exit(
            f"Тестовая БД недоступна ({settings.database_url}): {exc}. "
            "Запустите `docker compose up -d db`.",
            returncode=1,
        )


@pytest.fixture(scope="session")
async def engine(
    settings: Settings, migrated_database: None
) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(settings.database_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture(autouse=True)
async def clean_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE projects, tasks CASCADE"))


@pytest.fixture
async def client(
    settings: Settings, migrated_database: None
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def insert_task(session_factory: async_sessionmaker[AsyncSession]) -> InsertTask:
    async def insert(
        project_id: uuid.UUID,
        title: str = "Task",
        status: TaskStatus = TaskStatus.TO_DO,
    ) -> Task:
        task = Task.new(project_id, title)
        for next_status in STATUS_PATH[status]:
            task.change_status(next_status)

        async with session_factory() as session:
            session.add(TaskModel.from_domain(task))
            await session.commit()

        return task

    return insert
