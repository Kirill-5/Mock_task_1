# Design

## Context

Мотивация описана в proposal.md (раздел Why), требования — в `specs/projects/spec.md`.

Текущее состояние кода:
- `app/domain/entities.py`: `Project` — frozen dataclass, `Project.new()` обрезает пробелы, проверяет длины и превращает пустое `description` в `None`. `Task`, `TaskStatus`, `TaskPriority` уже есть.
- `app/domain/errors.py`: иерархия `NotFoundError` / `ConflictError` / `DomainValidationError` с конкретными ошибками (`ProjectNotFound`, `ProjectNameAlreadyExists`, `ProjectHasTasksInProgress`).
- `app/application/`: порты, команды и use cases `CreateProjectUseCase`, `GetProjectUseCase`, `DeleteProjectUseCase`. `DeleteProjectUseCase` вызывает `uow.tasks.has_tasks_in_progress()`.
- `app/infrastructure/uow.py`: `SqlAlchemyUnitOfWork`, импортирует пока несуществующие `SqlAlchemyProjectRepository` и `SqlAlchemyTaskRepository`.
- Нет `__init__.py`: пакеты namespace, импорты вида `app.domain...` работают от корня репозитория.
- `pyproject.toml` без зависимостей, `requires-python >=3.12`. Локальный `.venv` на Python 3.13, `uv` установлен. В `migrations/` только пустая `versions/`, `alembic.ini` нет. Docker и Compose доступны.

## Goals / Non-Goals

**Goals:**
- Рабочий вертикальный срез projects: HTTP → use case → репозиторий → PostgreSQL.
- Схема БД сразу содержит `tasks` с каскадом и уникальным индексом, чтобы change про задачи не менял ключи и индексы.
- Тестовая инфраструктура (БД, фикстуры, HTTP-клиент), которую переиспользует следующий change.

**Non-Goals:**
- Не меняем домен и use cases, даже если хочется поправить мелочи: правки только при обнаружении бага, отдельным пунктом.
- Не делаем generic-репозиторий или базовый класс CRUD: два репозитория, каждый под свой порт.

## Decisions

### D1. Зависимости через uv, группа dev для инструментов
Runtime: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]>=2.0`, `asyncpg`, `alembic`, `pydantic-settings`. Dev (`[dependency-groups] dev`): `pytest`, `pytest-asyncio`, `httpx`, `ruff`. `uv` уже установлен, а `pyproject.toml` создан через `uv init`. Альтернатива — `requirements.txt` и pip, но тогда нет lock-файла.

### D2. Настройки через pydantic-settings
`app/infrastructure/settings.py`: `Settings` с `database_url` (по умолчанию `postgresql+asyncpg://app:app@localhost:5432/app`) и `test_database_url` (`.../app_test`), чтение из env и `.env`. В `.env.example` — те же значения. Settings лежат в infrastructure: domain и application про них не знают.

### D3. docker-compose: один контейнер Postgres, две базы
Сервис `db` (`postgres:16`), порт 5432, healthcheck через `pg_isready`, volume для данных. Тестовая база `app_test` создаётся init-скриптом `docker/postgres/init.sql`, который монтируется в `/docker-entrypoint-initdb.d`. Альтернатива — отдельный контейнер для тестов: он тяжелее и даёт второй порт, а изоляции хватает и отдельной базы.

### D4. ORM-модели: SQLAlchemy 2.0 typed mapping
`app/infrastructure/db/models.py`: `Base(DeclarativeBase)` с `MetaData(naming_convention=...)`, чтобы имена ограничений в миграциях были стабильными.
- `ProjectModel` (`projects`): `id UUID PK`, `name VARCHAR(100) NOT NULL`, `description VARCHAR(1000) NULL`, `created_at TIMESTAMPTZ NOT NULL`. Индекс `ux_projects_name_lower` — `UNIQUE` на `lower(name)`.
- `TaskModel` (`tasks`): `id UUID PK`, `project_id UUID FK → projects.id ON DELETE CASCADE NOT NULL`, `title VARCHAR(200)`, `priority`, `status`, `created_at`, `updated_at TIMESTAMPTZ`. `priority` и `status` хранятся как `VARCHAR` с `CHECK`, а не как PG ENUM: так легче менять набор значений миграцией. Индексы: `UNIQUE (project_id, lower(title))`, `(project_id, created_at)` под будущий список задач, частичный `(project_id) WHERE status = 'in_progress'` не делаем — преждевременно.
- `from_domain()` / `to_domain()` на обеих моделях. ORM-связь `relationship` между моделями не объявляем: каскад делает БД, а навигация по связи не нужна ни одному порту.

`id` и `created_at` генерирует домен (`Project.new`), а не БД: сущность полна до сохранения, и use case может вернуть её без повторного чтения.

### D5. Репозитории: flush без commit, гонка уникальности → доменная ошибка
`app/infrastructure/db/repository.py`:
- `add`: `session.add(ProjectModel.from_domain(p))` + `flush()`. Если `flush` падает с `IntegrityError` по `ux_projects_name_lower` (между проверкой `exists_by_name` и вставкой успел вставить другой запрос), репозиторий бросает `ProjectNameAlreadyExists`. Так гонка тоже даёт 409, а не 500. Остальные `IntegrityError` пробрасываются как есть. Infrastructure может импортировать domain, правило зависимостей не нарушается.
- `get`: `session.get(ProjectModel, id)` → `to_domain()` или `None`.
- `exists_by_name`: `SELECT EXISTS(... WHERE lower(name) = lower(:name))`; использует тот же функциональный индекс.
- `delete`: `DELETE FROM projects WHERE id = :id` через Core-выражение + `flush()`. Core, а не `session.delete(model)`: доменный `Project` не привязан к сессии, а каскад на задачи выполняет БД.
- `SqlAlchemyTaskRepository.has_tasks_in_progress`: `SELECT EXISTS(... WHERE project_id = :id AND status = 'in_progress')`. Остальные методы порта не реализуются в этом change. Класс объявляет только то, что реализовано: мёртвые заглушки с `NotImplementedError` не добавляем.

### D6. Сессии и UoW в presentation
`app/infrastructure/db/session.py`: `create_engine(url)` и `create_session_factory(engine)` (`expire_on_commit=False`). В `app/main.py` фабрика `create_app(settings)` создаёт engine в lifespan и кладёт `uow_factory` в `app.state`. `app/presentation/deps.py`: `get_uow_factory(request)` и по функции-зависимости на use case (`get_create_project_use_case` и т. д.). Тесты подменяют `Settings` на тестовую БД через аргумент `create_app`, а не через `dependency_overrides`: так проверяется реальная сборка.

### D7. Валидация: домен — источник правды, Pydantic — только типы
`ProjectCreate(BaseModel)`: `name: str`, `description: str | None = None`, без `min_length` и `max_length`. Длины после обрезки проверяет `Project.new()` → `DomainValidationError` → 422. Если продублировать ограничения в Pydantic, правила разойдутся: `"  ab  "` прошёл бы `min_length=3`. Типовые ошибки (нет `name`, не строка, `id` не UUID) ловит FastAPI → стандартный 422.
`ProjectRead`: `id`, `name`, `description`, `created_at`; строится из доменного `Project` (`model_config = ConfigDict(from_attributes=True)`).

### D8. Маппинг ошибок в main.py
Три `exception_handler` на базовые классы: `NotFoundError` → 404, `ConflictError` → 409, `DomainValidationError` → 422. Тело — `{"detail": str(exc)}`, в одном формате с ошибками FastAPI. Обработчики на базовые классы, а не на каждую конкретную ошибку: новые ошибки задач замапятся автоматически.

### D9. Alembic async
`alembic.ini` в корне, `migrations/env.py` по шаблону `async`: URL берётся из `Settings` (env `DATABASE_URL` перекрывает), `target_metadata = Base.metadata`. `alembic init` не подходит, потому что каталог `migrations/` уже существует, поэтому `env.py` и `script.py.mako` пишутся вручную. Первая миграция создаётся `--autogenerate` и проверяется глазами: функциональные индексы по `lower()` и `ondelete="CASCADE"` должны попасть в неё явно.

### D10. Тесты на реальном PostgreSQL
- `tests/conftest.py`: session-фикстура один раз прогоняет `alembic upgrade head` на `app_test` (тем же кодом, что и CLI, через `alembic.command.upgrade`) — заодно это проверка миграции. Перед каждым тестом выполняется `TRUNCATE projects, tasks CASCADE`.
- `pytest-asyncio` в режиме `auto`, `asyncio_default_fixture_loop_scope = "session"` и `asyncio_default_test_loop_scope = "session"`, чтобы engine жил в одном event loop со всеми тестами.
- `tests/integration/test_project_repository.py`: репозиторий и индекс напрямую.
- `tests/api/test_projects.py`: `httpx.AsyncClient(transport=ASGITransport(app))`. Задачи для сценариев удаления вставляются фикстурой напрямую через `TaskModel.from_domain(Task.new(...))` (статус меняется через `task.change_status`), потому что роутов задач ещё нет.
- Конфигурация pytest в `pyproject.toml` (`[tool.pytest.ini_options]`, `pythonpath = ["."]`, `testpaths = ["tests"]`).

## Risks / Trade-offs

- [Тесты требуют поднятого Postgres] → `docker compose up -d db` в README-командах CLAUDE.md. Если БД недоступна, conftest падает с понятным сообщением, а не тихо пропускает тесты.
- [Autogenerate может потерять функциональный индекс или `ondelete`] → миграцию проверяет отдельная задача; тест на уникальность в хранилище и тест каскада ловят расхождение.
- [Гонка при создании с одинаковым именем] → закрыта D5: `IntegrityError` по индексу → `ProjectNameAlreadyExists` → 409.
- [Частичная реализация `SqlAlchemyTaskRepository`] → класс формально не удовлетворяет `TaskRepository` Protocol, а `SqlAlchemyUnitOfWork` объявляет `tasks: SqlAlchemyTaskRepository`. В рантайме это не важно: Protocol не проверяется. Если подключится type checker, расхождение будет видно. Закрывается change про задачи.
- [Локальный `.venv` на 3.13, а целевая версия 3.12] → `requires-python >=3.12` допускает обе; синтаксис 3.13+ не используем. Ruff `target-version = "py312"` в `pyproject.toml` подсветит лишнее.

## Migration Plan

Первая миграция на пустой БД: `docker compose up -d db` → `alembic upgrade head`. Откат: `alembic downgrade base` удаляет обе таблицы, данных в проде ещё нет.
