# Proposal

## Why

Домен, порты и use cases для проектов уже написаны, но приложение нельзя запустить: нет ORM-моделей, репозиториев, схемы БД, HTTP-слоя и окружения с PostgreSQL. `app/infrastructure/uow.py` импортирует несуществующий модуль `app.infrastructure.db.repository`. Этот change даёт первый работающий вертикальный срез — управление проектами через REST API — и инфраструктуру, на которую потом ляжут задачи.

## What Changes

- Зависимости проекта в `pyproject.toml` (FastAPI, SQLAlchemy async + asyncpg, Alembic, pydantic-settings, uvicorn; для разработки — pytest, pytest-asyncio, httpx, ruff).
- `docker-compose.yml` с PostgreSQL (рабочая и тестовая БД), настройки подключения через переменные окружения.
- ORM-модели `projects` и `tasks` с `from_domain()` / `to_domain()`; уникальный индекс по `lower(name)` для проектов, по `(project_id, lower(title))` для задач, внешний ключ `tasks.project_id` с `ON DELETE CASCADE`.
- `SqlAlchemyProjectRepository` — полная реализация порта `ProjectRepository`.
- `SqlAlchemyTaskRepository` — только метод `has_tasks_in_progress`, нужный для удаления проекта; этого хватает, чтобы `SqlAlchemyUnitOfWork` импортировался и работал.
- Настройка Alembic (async) и первая миграция, создающая обе таблицы.
- Presentation-слой: схемы Pydantic, зависимости FastAPI, роутер с `POST /projects`, `GET /projects/{id}`, `DELETE /projects/{id}`.
- `app/main.py`: сборка приложения и маппинг доменных ошибок в 404 / 409 / 422.
- Тесты: интеграционные тесты репозитория и API на PostgreSQL, по тесту на каждый Scenario из spec.

## Out of Scope

- Роуты `/projects/{id}/tasks` и `/tasks/...` (создание, список, получение, изменение задачи, смена статуса).
- Методы `SqlAlchemyTaskRepository`, кроме `has_tasks_in_progress`: `add`, `get`, `update`, `exists_by_title`, `list_by_project`, `count_by_project`. Остаются для change про задачи.
- Список проектов (`GET /projects`) и изменение проекта (`PATCH /projects/{id}`): их нет в API из CLAUDE.md.
- Изменения доменного слоя и существующих use cases: они используются как есть.
- Dockerfile и запуск самого API в контейнере: compose поднимает только PostgreSQL.
- Аутентификация, авторизация, CI.

## Capabilities

### New Capabilities
- `projects`: создание, получение и удаление проектов через REST API, правила валидации и уникальности имени, ограничения на удаление проекта с задачами.

### Modified Capabilities
<!-- нет -->

## Impact

- **Код:** новые `app/infrastructure/db/` (models, repository, session/settings), `app/presentation/` (schemas, deps, routers), `app/main.py`; правок в `app/domain` и `app/application` не требуется.
- **БД:** новые таблицы `projects` и `tasks`, миграция Alembic, `alembic.ini` и `migrations/env.py`.
- **API:** новые эндпоинты `POST /projects`, `GET /projects/{id}`, `DELETE /projects/{id}`.
- **Зависимости и окружение:** `pyproject.toml`, `docker-compose.yml`, `.env.example`; для тестов нужен запущенный PostgreSQL из compose.
