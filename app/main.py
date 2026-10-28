from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.errors import ConflictError, DomainValidationError, NotFoundError
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.settings import Settings
from app.infrastructure.uow import SqlAlchemyUnitOfWork
from app.presentation.routers import projects

ERROR_STATUS_CODES: dict[type[Exception], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    DomainValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def _error_handler(
    status_code: int,
) -> Callable[[Request, Exception], JSONResponse]:
    def handle(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(app_settings.database_url)
        session_factory = create_session_factory(engine)
        app.state.uow_factory = lambda: SqlAlchemyUnitOfWork(session_factory)
        yield
        await engine.dispose()

    app = FastAPI(title="Projects and tasks", lifespan=lifespan)
    app.include_router(projects.router)

    for error_class, status_code in ERROR_STATUS_CODES.items():
        app.add_exception_handler(error_class, _error_handler(status_code))

    return app


app = create_app()
