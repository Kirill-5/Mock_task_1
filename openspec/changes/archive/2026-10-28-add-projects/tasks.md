
# Tasks

## 1. Окружение и зависимости

- [x] 1.1 Добавить runtime-зависимости (`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`) и dev-группу (`pytest`, `pytest-asyncio`, `httpx`, `ruff`) через `uv add`; проверить: `uv sync` проходит, `uv.lock` создан
- [x] 1.2 Добавить в `pyproject.toml` `[tool.ruff]` с `target-version = "py312"` и `[tool.pytest.ini_options]` (`pythonpath = ["."]`, `testpaths = ["tests"]`, `asyncio_mode = "auto"`, loop scope `session` для фикстур и тестов); проверить: `ruff check .` и `pytest --collect-only` запускаются без ошибок конфигурации
- [x] 1.3 Создать `docker-compose.yml` с сервисом `db` (`postgres:16`, порт 5432, healthcheck `pg_isready`, volume) и `docker/postgres/init.sql`, создающий базу `app_test`; проверить: после `docker compose up -d db` команда `docker compose exec db psql -U app -l` показывает `app` и `app_test`
- [x] 1.4 Создать `app/infrastructure/settings.py` (`Settings`: `database_url`, `test_database_url`) и `.env.example`; проверить: `python -c "from app.infrastructure.settings import Settings; print(Settings())"` печатает URL по умолчанию
- [x] 1.5 Дополнить раздел «Команды» в CLAUDE.md командой `docker compose up -d db` и пометкой, что тестам нужна запущенная БД; проверить: команда из CLAUDE.md поднимает БД

## 2. ORM-модели, миграция и тестовая инфраструктура

- [x] 2.1 Создать `app/infrastructure/db/models.py`: `Base` с naming convention, `ProjectModel` (уникальный индекс по `lower(name)`), `TaskModel` (FK с `ON DELETE CASCADE`, уникальный индекс по `(project_id, lower(title))`, индекс `(project_id, created_at)`, `CHECK` для `status` и `priority`), `from_domain()` / `to_domain()` на обеих; проверить: модуль импортируется, `Base.metadata.tables` содержит `projects` и `tasks`
- [x] 2.2 Создать `app/infrastructure/db/session.py` (`create_engine`, `create_session_factory` с `expire_on_commit=False`); проверить: импорт без ошибок
- [x] 2.3 Настроить Alembic: `alembic.ini`, `migrations/env.py` (async, URL из `Settings`, `target_metadata = Base.metadata`), `migrations/script.py.mako`; проверить: `alembic current` подключается к БД без ошибок
- [x] 2.4 Сгенерировать первую миграцию `alembic revision --autogenerate -m "create projects and tasks"` и вручную сверить: функциональные уникальные индексы по `lower()`, `ondelete="CASCADE"`, `CHECK`-ограничения, корректный `downgrade`; проверить: `alembic upgrade head` → `alembic downgrade base` → `alembic upgrade head` проходят на чистой БД
- [x] 2.5 Создать `tests/conftest.py`: session-фикстура с `alembic upgrade head` на `app_test`, engine и session factory, autouse-фикстура `TRUNCATE projects, tasks CASCADE`, фикстура для вставки задачи нужного статуса напрямую через `TaskModel`; понятная ошибка, если БД недоступна; проверить: пустой тест с этими фикстурами проходит

## 3. Репозитории и Unit of Work

- [x] 3.1 Реализовать `SqlAlchemyProjectRepository` в `app/infrastructure/db/repository.py` (`add` с `flush` и переводом `IntegrityError` по `ux_projects_name_lower` в `ProjectNameAlreadyExists`, `get`, `exists_by_name` без учёта регистра, `delete` через Core `DELETE` + `flush`; без `commit`); проверить тестами из 3.3
- [x] 3.2 Реализовать `SqlAlchemyTaskRepository` только с `has_tasks_in_progress`; убедиться, что `app/infrastructure/uow.py` импортируется без правок; проверить тестами из 3.3
- [x] 3.3 Написать `tests/integration/test_project_repository.py`: `add` + `get` возвращают равный доменный `Project`; `get` неизвестного id → `None`; `exists_by_name` без учёта регистра; `has_tasks_in_progress` true/false; данные не видны другой сессии без `commit` UoW; проверить: тесты зелёные
- [x] 3.4 Тест на Scenario «Уникальность гарантируется на уровне хранилища»: две вставки `ProjectModel` с именами `"Alpha"` / `"alpha"` в обход use case → `IntegrityError`; плюс `add` через репозиторий на занятое имя → `ProjectNameAlreadyExists`; проверить: тест зелёный

## 4. HTTP API проектов

- [x] 4.1 Создать `app/presentation/schemas.py` (`ProjectCreate`: только типы, без ограничений длины; `ProjectRead` с `from_attributes=True`); проверить тестами из 4.5
- [x] 4.2 Создать `app/presentation/deps.py` (`get_uow_factory` из `app.state`, зависимости для `CreateProjectUseCase`, `GetProjectUseCase`, `DeleteProjectUseCase`); проверить тестами из 4.5
- [x] 4.3 Создать `app/presentation/routers/projects.py`: `POST /projects` → 201, `GET /projects/{project_id}` → 200, `DELETE /projects/{project_id}` → 204; `project_id: uuid.UUID`; проверить тестами из 4.5
- [x] 4.4 Создать `app/main.py`: `create_app(settings)` с lifespan (engine, `uow_factory` в `app.state`, `dispose` при остановке), подключение роутера, обработчики `NotFoundError` → 404, `ConflictError` → 409, `DomainValidationError` → 422 с телом `{"detail": ...}`, модульный `app = create_app()`; проверить: `uvicorn app.main:app` стартует, `/docs` открывается
- [x] 4.5 Добавить в `tests/conftest.py` фикстуру `client` (`httpx.AsyncClient` + `ASGITransport` поверх `create_app` с тестовыми настройками и запущенным lifespan); проверить: фикстура используется тестами 4.6–4.13

Тесты в `tests/api/test_projects.py`, по одному на каждый Scenario из `specs/projects/spec.md`:

- [x] 4.6 «Создание проекта»: тесты на Scenarios «Успешное создание проекта», «Создание без описания», «Обрезка пробелов»; проверить: зелёные
- [x] 4.7 «Валидация имени проекта»: тесты на «Слишком короткое имя», «Имя короче 3 символов после обрезки пробелов», «Слишком длинное имя», «Граничные длины имени», «Имя не передано»; для 422 проверить, что проект не создан; проверить: зелёные
- [x] 4.8 «Валидация описания проекта»: тесты на «Слишком длинное описание», «Описание максимальной длины»; проверить: зелёные
- [x] 4.9 «Уникальность имени проекта»: тесты на «Повтор имени в другом регистре», «Повтор имени с пробелами» (Scenario про хранилище покрыт в 3.4); проверить: зелёные
- [x] 4.10 «Получение проекта»: тесты на «Получение существующего проекта», «Проект не найден», «Некорректный идентификатор»; проверить: зелёные
- [x] 4.11 «Удаление проекта»: тесты на «Успешное удаление», «Удаление несуществующего проекта», «Удаление с некорректным идентификатором», «Имя освобождается после удаления»; проверить: зелёные
- [x] 4.12 «Запрет удаления проекта с задачами в работе»: тест на «Проект с задачей в работе» — 409, проект доступен по GET, задача осталась в БД; проверить: зелёный
- [x] 4.13 «Каскадное удаление задач проекта»: тесты на «Задачи в todo и done удаляются вместе с проектом», «Задачи других проектов не затрагиваются» (проверка через запрос к `tasks` в БД); проверить: зелёные

## 5. Финальная проверка

- [x] 5.1 `ruff check .` — без ошибок
  - Исключение из Non-Goals design.md: `ruff check --fix` в `app/domain/entities.py` (UP017, `datetime.UTC`) и `app/application/{commands,ports}.py` (I001, порядок импортов); поведение не меняется, отдельный коммит `style:`
- [x] 5.2 `ruff format --check .` — без изменений
- [x] 5.3 `pytest` — все тесты зелёные
- [x] 5.4 `alembic upgrade head` на чистой БД: `docker compose down -v && docker compose up -d db`, затем `alembic upgrade head` проходит без ошибок
