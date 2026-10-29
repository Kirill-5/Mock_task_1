# Tasks

## 1. Домен: пустое изменение задачи

- [x] 1.1 В `Task.update()` после проверки `done` бросать `DomainValidationError`, если `new_title` и `new_priority` оба `None` (design D1); проверить тестами из 1.2
- [x] 1.2 Написать `tests/unit/test_task_entity.py`: пустой `update` у задачи в `todo` → `DomainValidationError`, `updated_at` не изменился; пустой `update` у задачи в `done` → `TaskAlreadyDone`; проверить: тесты зелёные

## 2. Репозиторий задач

- [x] 2.1 Реализовать в `SqlAlchemyTaskRepository` методы `add` (`flush`, `IntegrityError` по `TASK_TITLE_UNIQUE_INDEX` → `TaskTitleAlreadyExists`), `get`, `exists_by_title` (`project_id` + `lower(title)`), `update` (Core `UPDATE` + `flush`, тот же перевод `IntegrityError`), без `commit` (design D2); проверить тестами из 2.2–2.3
- [x] 2.2 Написать `tests/integration/test_task_repository.py`: `add` + `get` возвращают равный `Task`; `get` неизвестного id → `None`; `exists_by_title` без учёта регистра и только в своём проекте; `update` сохраняет `title`, `priority`, `status`, `updated_at`; `add` и `update` на занятый `title` → `TaskTitleAlreadyExists`; проверить: тесты зелёные
- [x] 2.3 Тест на Scenario «Уникальность гарантируется на уровне хранилища»: две прямые вставки `TaskModel` в один проект с `title` `"Write spec"` / `"write spec"` → `IntegrityError`; проверить: тест зелёный

## 3. HTTP API задач

- [x] 3.1 Добавить в `app/presentation/schemas.py` `TaskCreate`, `TaskUpdate`, `TaskStatusChange`, `TaskRead` (только типы, enum из домена, `TaskRead` с `from_attributes=True`); у `TaskCreate`, `TaskUpdate`, `TaskStatusChange` и существующей `ProjectCreate` — `extra="forbid"` (design D3); проверить тестами из 3.5–3.15
- [x] 3.2 Добавить в `app/presentation/deps.py` `get_create_task_use_case`, `get_get_task_use_case`, `get_update_task_use_case`, `get_change_task_status_use_case`; проверить тестами из 3.5–3.14
- [x] 3.3 Создать `app/presentation/routers/tasks.py` (`APIRouter(tags=["tasks"])` без префикса): `POST /projects/{project_id}/tasks` → 201, `GET /tasks/{task_id}` → 200, `PATCH /tasks/{task_id}` → 200, `POST /tasks/{task_id}/status` → 200, ответы `TaskRead`, id типа `uuid.UUID` (design D4); подключить роутер в `app/main.py`; проверить: эндпоинты видны в `/openapi.json` и тестами из 3.5–3.14
- [x] 3.4 Создать `tests/api/test_tasks.py` с хелперами: создать проект, создать задачу, сдвинуть `updated_at` задачи в прошлое прямым `UPDATE` в БД (design, раздел Risks); проверить: хелперы используются тестами 3.5–3.14

Тесты в `tests/api/test_tasks.py`, по одному на каждый Scenario из `specs/tasks/spec.md`:

- [x] 3.5 «Создание задачи»: тесты на Scenarios «Успешное создание задачи», «Приоритет по умолчанию», «Обрезка пробелов в title», «Статус при создании задать нельзя» (422, задача не создана); проверить: зелёные
- [x] 3.6 «Создание задачи в несуществующем проекте»: тесты на «Проект не найден» (404, задач в БД нет), «Некорректный идентификатор проекта»; проверить: зелёные
- [x] 3.7 «Валидация title задачи»: тесты на «Слишком короткий title» (задача не создана), «Title короче 3 символов после обрезки пробелов», «Слишком длинный title», «Граничные длины title», «Title не передан», «Некорректный title при изменении» (`title` не изменился); проверить: зелёные
- [x] 3.8 «Валидация priority задачи»: тесты на «Недопустимый priority при создании», «Недопустимый priority при изменении»; проверить: зелёные
- [x] 3.9 «Уникальность title внутри проекта»: тесты на «Повтор title в другом регистре», «Одинаковый title в разных проектах», «Изменение title на занятый», «Изменение регистра собственного title» (Scenario про хранилище покрыт в 2.3); проверить: зелёные
- [x] 3.10 «Получение задачи»: тесты на «Получение существующей задачи», «Задача не найдена», «Некорректный идентификатор задачи»; проверить: зелёные
- [x] 3.11 «Изменение задачи»: тесты на «Изменение title» (`updated_at` строго больше прежнего), «Изменение priority», «Изменение title и priority одновременно», «Пустое изменение» (оба варианта тела, `updated_at` не изменился), «Попытка сменить статус через PATCH» (422, `status` и `updated_at` не изменились), «Изменение несуществующей задачи», «Изменение с некорректным идентификатором»; проверить: зелёные
- [x] 3.12 «Запрет изменения задачи в done»: тесты на «Изменение задачи в done» (`title` и `updated_at` не изменились), «Пустое изменение задачи в done», «Ошибка формы тела у задачи в done» (оба варианта тела → 422, задача не изменилась), «Некорректная длина title у задачи в done» (409); проверить: зелёные
- [x] 3.13 «Смена статуса задачи»: тесты на «Взять задачу в работу» (`updated_at` строго больше прежнего), «Завершить задачу», «Вернуть задачу в todo», «Лишнее поле при смене статуса» (422, статус остался `todo`); проверить: зелёные
- [x] 3.14 «Запрещённые переходы статуса»: тесты на «Пропуск in_progress», «Переход в текущий статус», «Переход из done» (оба целевых статуса), «Недопустимое значение статуса» (`"archived"` и `{}`), «Смена статуса несуществующей задачи», «Смена статуса с некорректным идентификатором»; проверить: зелёные
- [x] 3.15 MODIFIED «Создание проекта» (capability `projects`): тест в `tests/api/test_projects.py` на Scenario «Лишнее поле в теле» — `POST /projects` с `{"name": "Alpha", "owner": "bob"}` → 422, проект не создан; проверить: тест зелёный, существующие тесты проектов не сломались

## 4. Финальная проверка

- [x] 4.1 `ruff check .` — без ошибок
- [x] 4.2 `ruff format --check .` — без изменений
- [x] 4.3 `pytest` — все тесты зелёные, включая существующие тесты проектов
- [x] 4.4 `alembic upgrade head` на чистой БД: `docker compose down -v && docker compose up -d db`, затем `alembic upgrade head` проходит без ошибок, `alembic revision --autogenerate` не находит изменений схемы (сгенерированный пустой файл удалить)

## Workflow follow-up

- Синхронизировать specs `tasks` и `projects` в `openspec/specs/` и заархивировать change после ревью.
- Открыть PR из `feat/add-tasks` в `main`.
