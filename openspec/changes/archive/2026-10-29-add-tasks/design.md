# Design

## Context

Мотивация — в proposal.md (раздел Why), требования — в `specs/tasks/spec.md`.

Что уже есть в коде:
- `app/domain/entities.py`:
  - `Task.new()` обрезает пробелы и проверяет `title` и `priority`, статус ставит `todo`;
  - `Task.change_status()` проверяет `ALLOWED_STATUS_TRANSITIONS` и бросает `InvalidStatusTransition` (409);
  - `Task.update()` сначала проверяет `done` и бросает `TaskAlreadyDone` (409), потом нормализует поля и всегда обновляет `updated_at`.
- `app/application/use_cases.py`: готовы `CreateTaskUseCase`, `GetTaskUseCase`, `UpdateTaskUseCase`, `ChangeTaskStatusUseCase`.
  - `CreateTaskUseCase` вызывает `Task.new()` до проверки проекта, поэтому некорректный `title` даёт 422 даже для несуществующего проекта.
  - `UpdateTaskUseCase` проверяет уникальность, только если `title` поменялся не только регистром (`casefold`).
- `app/infrastructure/db/repository.py`: `SqlAlchemyTaskRepository` умеет только `has_tasks_in_progress`. У `SqlAlchemyProjectRepository` есть образец: `add` переводит `IntegrityError` по уникальному индексу в доменную ошибку через `_violated_constraint`.
- `app/infrastructure/db/models.py`: в `TaskModel` уже есть индекс `TASK_TITLE_UNIQUE_INDEX` (`ux_tasks_project_id_title_lower`), `CHECK` на `status` и `priority` и каскад. Миграция применена.
- `app/presentation/schemas.py`: `ProjectCreate` использует поведение Pydantic по умолчанию (`extra="ignore"`) и молча принимает лишние поля.
- `app/main.py` мапит базовые классы ошибок. Новые ошибки задач уже наследуют `NotFoundError` и `ConflictError`, поэтому отдельные обработчики не нужны.
- `tests/conftest.py`: фикстуры `client`, `session_factory` и `insert_task(project_id, title, status)`. Последняя пишет задачу нужного статуса напрямую в БД.

## Goals / Non-Goals

**Goals:**
- Подключить готовые use cases к HTTP с минимальными правками домена и application.
- Свести уникальность `title` к 409 и в обычном случае, и при гонке.

**Non-Goals:**
- Не трогаем `ListProjectTasksUseCase`, `list_by_project` и `count_by_project`: это следующий change.
- Не переписываем `CreateTaskUseCase` ради порядка проверок (422 раньше 404): spec этот порядок не фиксирует.
- Не добавляем ORM-`relationship` и generic-репозиторий.

## Decisions

### D1. Пустой `PATCH` отклоняет домен, а не Pydantic
В `Task.update()` после проверки `done`, но до нормализации полей: если `new_title is None and new_priority is None`, метод бросает `DomainValidationError`. Так соблюдается приоритет из spec: для задачи в `done` любое тело даёт 409, для остальных пустое тело даёт 422. Заодно `updated_at` не меняется без реального изменения.
Альтернатива — `model_validator` в `TaskUpdate`. Она отклонена: Pydantic отработал бы до use case и вернул бы 422 для задачи в `done` вместо 409. Кроме того, правило «нужно хотя бы одно поле» описывает сам метод сущности, а не формат HTTP-запроса.

### D2. Методы `SqlAlchemyTaskRepository`
- `add`: `session.add(TaskModel.from_domain(task))` + `flush()`. `IntegrityError` по `TASK_TITLE_UNIQUE_INDEX` превращается в `TaskTitleAlreadyExists`, остальные пробрасываются. Повторяет `SqlAlchemyProjectRepository.add` и переиспользует `_violated_constraint`.
- `get`: `session.get(TaskModel, id)` → `to_domain()` или `None`.
- `exists_by_title(project_id, title)`: `SELECT EXISTS(... WHERE project_id = :pid AND lower(title) = lower(:title))`. Попадает в тот же функциональный индекс.
- `update(task)`: Core-выражение `update(TaskModel).where(TaskModel.id == task.id).values(title, priority, status, updated_at)` + `flush()`, с тем же переводом `IntegrityError` в `TaskTitleAlreadyExists`. Core выбран для единообразия с `SqlAlchemyProjectRepository.delete`: доменный `Task` не привязан к сессии, а явный `UPDATE` не зависит от того, что лежит в identity map.
  Альтернатива — `session.merge(TaskModel.from_domain(task))`. Она тоже работает, но неявно делает `SELECT` и копирует все поля, включая неизменяемые `project_id` и `created_at`.

Всё это `async`, без `commit()`. После change класс реализует порт целиком, кроме `list_by_project` и `count_by_project`.

### D3. Схемы Pydantic: только типы, enum из домена, лишние поля запрещены
- `TaskCreate`: `title: str`, `priority: TaskPriority = TaskPriority.MEDIUM`.
- `TaskUpdate`: `title: str | None = None`, `priority: TaskPriority | None = None`. Явный `null` равен отсутствию поля.
- `TaskStatusChange`: `status: TaskStatus`.
- `TaskRead`: `id`, `project_id`, `title`, `priority`, `status`, `created_at`, `updated_at`, `from_attributes=True`. `StrEnum` сериализуется строкой.

Все входные схемы (`TaskCreate`, `TaskUpdate`, `TaskStatusChange` и существующая `ProjectCreate`) объявляют `model_config = ConfigDict(extra="forbid")`. Опечатка в имени поля или попытка передать `status` при создании или через `PATCH` не должна молча проходить: клиент получает стандартный 422 FastAPI. Схемы ответов (`TaskRead`, `ProjectRead`) остаются без `forbid`.
Альтернатива — `extra="ignore"` (по умолчанию). Она отклонена: `{"status": "done"}` в `PATCH` вернул бы 200 без изменений, и клиент решил бы, что статус сменился.

Длины `title` не дублируем в Pydantic, как и в D7 change про проекты: их проверяет домен после обрезки. Недопустимые значения enum, не-строковые значения, отсутствие обязательных полей и лишние поля ловит FastAPI.

Порядок проверок, из которого следуют коды ответа:
1. Pydantic: форма тела и тип id → 422.
2. Use case: существование задачи или проекта → 404.
3. Домен: `done` → 409, пустое изменение и длины `title` → 422.

Поэтому для задачи в `done` тело `{"priority": "urgent"}` даёт 422, а `{"title": "ab"}` и `{}` — 409. D1 остаётся верным: `{}` проходит Pydantic и доходит до домена.
Presentation импортирует enum из domain. Это направление внутрь, и так уже делают `commands.py`.

### D4. Один роутер `routers/tasks.py` с полными путями
`router = APIRouter(tags=["tasks"])` без префикса:
- `POST /projects/{project_id}/tasks` → 201;
- `GET /tasks/{task_id}` → 200;
- `PATCH /tasks/{task_id}` → 200;
- `POST /tasks/{task_id}/status` → 200.

Все ответы — `TaskRead`. Будущий `GET /projects/{id}/tasks` ляжет в этот же файл.
Альтернатива — положить создание в `projects.py`. Она отклонена: роутер проектов начал бы зависеть от task-схем и use cases, а задачи разъехались бы по двум файлам.
Зависимости в `deps.py`: `get_create_task_use_case`, `get_get_task_use_case`, `get_update_task_use_case`, `get_change_task_status_use_case`, по образцу проектов. `app/main.py` добавляет `app.include_router(tasks.router)`.

### D5. Тесты
- `tests/integration/test_task_repository.py`:
  - `add` + `get` возвращают равный `Task`; `get` неизвестного id → `None`;
  - `exists_by_title` без учёта регистра и только в своём проекте;
  - `update` сохраняет изменения; `add` и `update` на занятый `title` → `TaskTitleAlreadyExists`;
  - две прямые вставки `TaskModel` с `title`, отличающимися регистром, → `IntegrityError` (Scenario про хранилище).
- Юнит-тест домена `tests/unit/test_task_entity.py` на D1: пустой `update` → `DomainValidationError`, для `done` → `TaskAlreadyDone`, `updated_at` не меняется.
- `tests/api/test_projects.py`: тест на Scenario «Лишнее поле в теле» из MODIFIED-требования `projects`.
- `tests/api/test_tasks.py`: по тесту на каждый Scenario. Задачи в `in_progress` и `done` создаются через API (`POST /tasks/{id}/status`), там где проверяется переход, и через `insert_task`, где статус — только предусловие.

## Risks / Trade-offs

- [Проверка «`updated_at` больше прежнего» может мигать: при грубом таймере два вызова `datetime.now(UTC)` вернут одно значение] → перед изменением тест сдвигает `updated_at` задачи в прошлое прямым `UPDATE` в БД и затем сравнивает строго.
- [`UpdateTaskUseCase` сравнивает `casefold()`, а БД — `lower()`; они расходятся на редких символах вроде `ß`] → индекс всё равно не пропустит дубликат, а D2 переведёт `IntegrityError` в 409. Отдельно не чиним.
- [BREAKING для клиентов `POST /projects`, которые шлют лишние поля] → других клиентов, кроме тестов, нет; существующие тесты лишних полей не передают; изменение зафиксировано в proposal.
- [Порядок проверок при создании: 422 за `title` раньше 404 за проект] → закреплено в Context. Сценарии 404 в spec используют корректный `title`.
- [`SqlAlchemyTaskRepository` всё ещё не полностью удовлетворяет Protocol `TaskRepository`] → закроется в change про список задач. Protocol в рантайме не проверяется.

## Migration Plan

Схема БД не меняется, новых миграций нет. Развёртывание — обычный деплой кода. Откат — откат кода, данные совместимы.
