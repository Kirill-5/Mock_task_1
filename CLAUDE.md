# Mock Task 1: проекты и задачи

REST API для управления проектами и их задачами. Построен по Clean Architecture.

## Стек
Python 3.12, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL, Alembic, Pydantic v2, pytest, Docker Compose.

## Команды
- Поднять PostgreSQL (рабочая `app` и тестовая `app_test` базы): `docker compose up -d db`
- Запуск API: `uvicorn app.main:app --reload`
- Тесты: `pytest` (нужна запущенная БД: `docker compose up -d db`)
- Линтер и форматирование: `ruff check .` / `ruff format .`
- Применить миграции: `alembic upgrade head`
- Новая миграция: `alembic revision --autogenerate -m "<описание>"`

## Архитектура
Зависимости направлены только внутрь: `presentation → application → domain`, `infrastructure → application → domain`.
Слой domain не импортирует ничего из других слоёв и сторонних библиотек.

- `app/domain/`: сущности, бизнес-правила, доменные ошибки. Только Python.
  - Сущности — dataclass, создаются через `Entity.new(...)`, который нормализует и проверяет данные.
  - Состояние меняется только через методы сущности (`Task.change_status`, `Task.update`), а не прямым присваиванием полей.
- `app/application/`: use cases и порты.
  - `ports.py`: интерфейсы репозиториев и `UnitOfWork` на `Protocol`.
  - `commands.py`: команды, запросы и результаты — frozen dataclass.
  - `use_cases.py`: класс на каждый сценарий, в конструкторе `UowFactory`, метод `execute()`.
- `app/infrastructure/`: реализации на SQLAlchemy.
  - `db/models.py`: ORM-модели с `from_domain()` / `to_domain()`.
  - `db/repository.py`: репозитории делают `flush()`, но никогда `commit()`.
  - `uow.py`: `SqlAlchemyUnitOfWork`. Use case коммитит явно, `__aexit__` всегда откатывает незакоммиченное.
- `app/presentation/`: схемы Pydantic, зависимости FastAPI (`deps.py`), роутеры.
- `app/main.py`: сборка приложения и маппинг доменных ошибок в HTTP-коды.

## Соглашения
- Все методы репозиториев и UoW — `async`.
- Use case бросает только доменные ошибки и ничего не знает про HTTP.
- Маппинг ошибок: `NotFoundError` → 404, `ConflictError` → 409, `DomainValidationError` → 422.
- Уникальность проверяется в use case и гарантируется уникальным индексом в БД.
- Без комментариев, которые пересказывают код.

## Правила домена
**Project:** `name` 3–100 символов, пробелы по краям обрезаются, уникально без учёта регистра; `description` необязательное, до 1000 символов.

**Task:** `title` 3–200 символов, пробелы обрезаются, уникально без учёта регистра внутри проекта;
`priority` low / medium / high (по умолчанию medium); `status` todo / in_progress / done (при создании всегда todo).

1. Разрешённые переходы статуса: todo → in_progress, in_progress → done, in_progress → todo.
2. Задачу в `done` нельзя изменять.
3. Проект нельзя удалить, пока в нём есть задачи в `in_progress`.
4. При удалении проекта удаляются его задачи (`ON DELETE CASCADE`).

## API
| Метод | Путь | Что делает |
|---|---|---|
| POST | `/projects` | Создать проект |
| GET | `/projects/{id}` | Получить проект |
| DELETE | `/projects/{id}` | Удалить проект |
| POST | `/projects/{id}/tasks` | Создать задачу в проекте |
| GET | `/projects/{id}/tasks` | Список задач проекта |
| GET | `/tasks/{id}` | Получить задачу |
| PATCH | `/tasks/{id}` | Изменить title и/или priority |
| POST | `/tasks/{id}/status` | Сменить статус задачи |

Список задач: необязательные фильтры `status`, `priority`; `limit` 1–100 (по умолчанию 20), `offset` ≥ 0 (по умолчанию 0);
сортировка по `created_at` от новых к старым; ответ `{items, total, limit, offset}`.