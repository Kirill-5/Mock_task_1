# Proposal

## Why

Проекты уже работают через REST API, а задачи — нет. Домен (`Task`, переходы статуса, запрет изменять `done`), команды и use cases для задач написаны, но `SqlAlchemyTaskRepository` реализует только `has_tasks_in_progress`, и HTTP-роутов для задач нет. Этот change даёт рабочий вертикальный срез для одной задачи: создание, получение, изменение и смена статуса.

## What Changes

- `SqlAlchemyTaskRepository`: методы `add`, `get`, `update`, `exists_by_title`. Если гонка нарушает уникальный индекс `(project_id, lower(title))`, репозиторий бросает `TaskTitleAlreadyExists`, и клиент получает 409, а не 500.
- Домен: `Task.update()` бросает `DomainValidationError`, когда не передано ни `title`, ни `priority`. Пустой `PATCH` даёт 422. Проверка статуса `done` идёт первой, поэтому для задачи в `done` по-прежнему 409.
- **BREAKING** (`POST /projects`): тело с неизвестными полями теперь даёт 422, раньше такие поля молча игнорировались. Все схемы тел запросов задач тоже отклоняют неизвестные поля с 422, поэтому `status` нельзя передать при создании задачи или через `PATCH`.
- Presentation: схемы `TaskCreate`, `TaskUpdate`, `TaskStatusChange`, `TaskRead`; зависимости для `CreateTaskUseCase`, `GetTaskUseCase`, `UpdateTaskUseCase`, `ChangeTaskStatusUseCase`.
- Новые эндпоинты:
  - `POST /projects/{id}/tasks` — 201;
  - `GET /tasks/{id}` — 200;
  - `PATCH /tasks/{id}` — 200;
  - `POST /tasks/{id}/status` — 200.
- Тесты: интеграционные тесты репозитория задач и API-тесты, по тесту на каждый Scenario из spec.

## Out of Scope

- Список задач проекта `GET /projects/{id}/tasks`: фильтры `status` и `priority`, пагинация `limit`/`offset`, сортировка, ответ `{items, total, limit, offset}`. Также методы репозитория `list_by_project` и `count_by_project` и подключение `ListProjectTasksUseCase` к HTTP. Это отдельный change.
- Удаление задачи и перенос задачи в другой проект: их нет в API из CLAUDE.md.
- Изменение статуса через `PATCH /tasks/{id}`: статус меняется только через `POST /tasks/{id}/status`.
- Изменения схемы БД и новые миграции: таблица `tasks`, индексы и каскад уже созданы первой миграцией.
- Прочие изменения capability `projects`: меняется только реакция `POST /projects` на неизвестные поля; требования к удалению проекта с задачами остаются прежними.
- Правки доменного слоя и use cases сверх проверки пустого `update`.

## Capabilities

### New Capabilities
- `tasks`: создание задачи в проекте, получение, изменение `title` и `priority`, смена статуса по разрешённым переходам; правила валидации, уникальность `title` внутри проекта и запрет изменять задачу в `done`.

### Modified Capabilities
- `projects`: `POST /projects` с неизвестными полями в теле отвечает 422.

## Impact

- **Код:**
  - `app/domain/entities.py`: проверка пустого `update`;
  - `app/infrastructure/db/repository.py`: методы `SqlAlchemyTaskRepository`;
  - `app/presentation/`: `schemas.py` (новые схемы задач, `extra="forbid"` у `ProjectCreate`), `deps.py`, новый `routers/tasks.py`;
  - `app/main.py`: подключение роутера.
- **API:** новые эндпоинты `POST /projects/{id}/tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, `POST /tasks/{id}/status`; `POST /projects` строже к телу запроса (**BREAKING**).
- **БД:** без изменений.
- **Зависимости:** без изменений.
