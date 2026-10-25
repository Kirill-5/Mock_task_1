from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.repository import SqlAlchemyProjectRepository , SqlAlchemyTaskRepository


class SqlAlchemyUnitOfWork:
    projects: SqlAlchemyProjectRepository
    tasks: SqlAlchemyTaskRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None


    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.project = SqlAlchemyProjectRepository(self._session)
        self.task = SqlAlchemyTaskRepository(self._session)
        return self


    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._get_session()
        try:
            await session.rollback()
        finally:
            await session.close()
            self._session = None

    async def commit(self) -> None:
        await self._get_session().commit()

    async def rollback(self) -> None:
        await self._get_session().rollback()

    def _get_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not started, use 'async with'")
        return self._session