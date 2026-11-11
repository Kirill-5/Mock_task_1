# Design

## Context

Мотивация — в proposal.md (раздел Why), требования — в `specs/tasks/spec.md`.

Что уже есть в коде:
- `app/application/ports.py`: в `TaskRepository` объявлены `list_by_project(project_id, *, status, priority, limit, offset) -> list[Task]` и `count_by_project(project_id, *, status, priority) -> int`.
- `app/application/commands.py`: `ListProjectTasks` (фильтры и пагинация с дефолтами `limit=20`, `offset=0`) и `TaskPage(items, total, offset, limit)`.
- `app/application/use_cases.py`: `ListProjectTasksUseCase` проверяет проект (`ProjectNotFound` → 404), вызывает `list_by_project` и `count_by_project` с одинаковыми фильтрами в одном UoW и собирает `TaskPage`. Диапазоны `limit` и `offset` не проверяет.
- `app/infrastructure/db/repository.py`: в `SqlAlchemyTaskRepository` нет `list_by_project` и `count_by_project`.
- `app/infrastructure/db/models.py`: индекс `ix_tasks_project_id_created_at (project_id, created_at)` уже есть в миграции.
- `app/presentation/routers/tasks.py`: роутер без префикса с полными путями, рядом `POST /projects/{project_id}/tasks`.
- `tests/conftest.py`: фикстуры `client`, `session_factory`, `insert_task(project_id, title, status)`.

## Goals / Non-Goals

**Goals:**
- Реализовать два метода порта так, чтобы `items` и `total` всегда считались по одним и тем же условиям.
- Детерминированный порядок, при котором страницы не пересекаются.

**Non-Goals:**
- Не меняем `ListProjectTasksUseCase`, `ListProjectTasks` и `TaskPage`.
- Не добавляем новые индексы и миграции.
- Не вводим общий механизм пагинации для других ресурсов: список пока один.

## Decisions

### D1. Общая функция условий для list и count
Модульная функция в `repository.py` возвращает список условий `WHERE`: всегда `project_id = :pid`, плюс `status = :status` и `priority = :priority`, если фильтр не `None`. В условия идут `.value` enum, как в `update` и `has_tasks_in_progress`.
- `list_by_project`: `select(TaskModel).where(*conditions).order_by(created_at.desc(), id.desc()).limit(limit).offset(offset)`, результат через `to_domain()`.
- `count_by_project`: `select(func.count()).select_from(TaskModel).where(*conditions)`.

Одна функция условий гарантирует, что `total` не разойдётся с `items` при добавлении нового фильтра.
Альтернатива — один запрос с `count(*) OVER ()`. Отклонена: порт и use case уже разделены на два метода, а при `offset` за концом списка оконная функция не вернёт строк, и `total` пришлось бы получать отдельно.

### D2. Сортировка: `created_at DESC, id DESC`
`created_at` задаёт порядок из CLAUDE.md, `id` — тай-брейкер. Без него при одинаковом `created_at` (например, пакетная вставка) PostgreSQL может отдавать строки в разном порядке на разных страницах, и задача попадёт на две страницы или не попадёт ни на одну. Индекс `(project_id, created_at)` покрывает фильтр по проекту и основную сортировку.
Альтернатива — сортировать только по `created_at`. Отклонена: нестабильность пагинации — реальный, хоть и редкий баг, а цена — одно поле в `ORDER BY`.

### D3. Query-параметры через `Annotated` + `Query`
В сигнатуре роута:
- `status: TaskStatus | None = None`, `priority: TaskPriority | None = None` — enum из домена, недопустимое значение даёт 422 средствами FastAPI;
- `limit: Annotated[int, Query(ge=1, le=100)] = 20`, `offset: Annotated[int, Query(ge=0)] = 0`.

Диапазоны `limit` и `offset` — это ограничение HTTP-контракта, поэтому они в presentation, а не в домене или use case. Значения по умолчанию совпадают с дефолтами `ListProjectTasks`.
Альтернатива — Pydantic-модель для query-параметров с `extra="forbid"`. Отклонена в этом change: тогда пришлось бы решать, отклонять ли неизвестные параметры, а это вне scope (proposal). Неизвестные параметры игнорируются, как по умолчанию в FastAPI.

### D4. Схема ответа `TaskPageRead`
`TaskPageRead`: `items: list[TaskRead]`, `total: int`, `limit: int`, `offset: int`, `from_attributes=True`. Тогда роут возвращает `TaskPageRead.model_validate(page)` прямо из `TaskPage`, а вложенные `Task` превращаются в `TaskRead` так же, как в остальных ручках.

### D5. Роут и зависимость
- `routers/tasks.py`: `GET /projects/{project_id}/tasks` → 200, `response_model=TaskPageRead`, `project_id: uuid.UUID` (не UUID → 422).
- `deps.py`: `get_list_project_tasks_use_case`, по образцу остальных.
- `main.py` не меняется: роутер задач уже подключён.

### D6. Тесты
- `tests/integration/test_task_repository.py`: только задачи своего проекта; фильтр по `status`, по `priority` и оба вместе; `count_by_project` с теми же фильтрами; порядок `created_at DESC`; стабильный порядок при одинаковом `created_at`; `limit`/`offset`; `offset` за концом → пустой список.
- `tests/api/test_tasks.py`: по тесту на каждый Scenario из `specs/tasks/spec.md`.
- Порядок проверяется по явно заданным `created_at`: тест после вставки задач выставляет `created_at` прямым `UPDATE` в БД (как `backdate_task` для `updated_at`). Равные `created_at` для Scenario про стабильность задаются тем же способом.

## Risks / Trade-offs

- [`items` и `total` считаются двумя запросами: при параллельной записи в READ COMMITTED они могут кратко разойтись] → для этого API допустимо; оба запроса идут в одном UoW друг за другом. REPEATABLE READ не вводим.
- [Большой `offset` заставляет БД пропускать строки] → `limit` ограничен 100, проекты небольшие. Курсорная пагинация — вне scope.
- [Тай-брейкер `id` не входит в индекс] → при сортировке внутри одного проекта дополнительная сортировка по `id` нужна только для строк с равным `created_at`, это дёшево.
- [Диапазоны `limit` и `offset` проверяет только HTTP-слой; вызов use case из другого места с `limit=0` вернёт пустой список] → сейчас use case вызывается только из роута. Если появятся другие входы, проверку можно перенести в `ListProjectTasks`.

## Migration Plan

Схема БД не меняется, новых миграций нет. Развёртывание — обычный деплой кода. Откат — откат кода.
