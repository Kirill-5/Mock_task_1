# Tasks

## 1. Репозиторий задач: список и количество

- [x] 1.1 В `app/infrastructure/db/repository.py` добавить модульную функцию условий фильтрации (`project_id` + необязательные `status`, `priority` через `.value`) и методы `SqlAlchemyTaskRepository.list_by_project` (`ORDER BY created_at DESC, id DESC`, `LIMIT`/`OFFSET`, `to_domain()`) и `count_by_project` (`count(*)` по тем же условиям), без `commit` (design D1, D2); проверить тестами из 1.2
- [x] 1.2 В `tests/integration/test_task_repository.py` добавить тесты: в список попадают только задачи своего проекта; фильтр по `status`, по `priority` и оба вместе; `count_by_project` возвращает число с теми же фильтрами; порядок по `created_at` от новых к старым; при равном `created_at` порядок стабилен и страницы `limit=2` по `offset` 0/2/4 дают все задачи ровно по разу; `offset` за концом → пустой список; проверить: тесты зелёные

## 2. HTTP: GET /projects/{id}/tasks

- [x] 2.1 Добавить в `app/presentation/schemas.py` `TaskPageRead` (`items: list[TaskRead]`, `total`, `limit`, `offset`, `from_attributes=True`) (design D4); проверить тестами из 2.4–2.8
- [x] 2.2 Добавить в `app/presentation/deps.py` `get_list_project_tasks_use_case` по образцу остальных; проверить тестами из 2.4–2.8
- [x] 2.3 Добавить в `app/presentation/routers/tasks.py` роут `GET /projects/{project_id}/tasks` → 200, `response_model=TaskPageRead`, query-параметры `status: TaskStatus | None`, `priority: TaskPriority | None`, `limit` (1–100, по умолчанию 20), `offset` (≥ 0, по умолчанию 0) через `Annotated` + `Query` (design D3, D5); проверить: эндпоинт виден в `/openapi.json` и тестами из 2.4–2.8
- [x] 2.4 Добавить в `tests/api/test_tasks.py` хелпер, выставляющий `created_at` задачи прямым `UPDATE` в БД (design D6); проверить: используется тестами 2.5–2.7

Тесты в `tests/api/test_tasks.py`, по одному на каждый Scenario из `specs/tasks/spec.md`:

- [x] 2.5 «Список задач проекта»: тесты на Scenarios «Список задач проекта» (только задачи проекта A, формат задачи, `total` = 3, дефолтные `limit` = 20 и `offset` = 0) и «Проект без задач»; проверить: зелёные
- [x] 2.6 «Сортировка списка задач»: тесты на «Новые задачи первыми» и «Стабильный порядок при одинаковом created_at» (все пять задач ровно по разу, повтор запросов даёт тот же порядок); проверить: зелёные
- [x] 2.7 «Фильтрация списка задач»: тесты на «Фильтр по статусу», «Фильтр по приоритету», «Оба фильтра вместе», «Недопустимое значение фильтра» (`status=archived` и `priority=urgent` → 422); проверить: зелёные
- [x] 2.8 «Пагинация списка задач»: тесты на «Страница задач», «Offset за пределами списка», «Граничные значения limit» (1 и 100), «Недопустимые limit и offset» (`limit=0`, `limit=101`, `limit=abc`, `offset=-1` → 422); проверить: зелёные
- [x] 2.9 «Список задач несуществующего проекта»: тесты на «Проект не найден» (404) и «Некорректный идентификатор проекта» (422); проверить: зелёные

## 3. Финальная проверка

- [x] 3.1 `ruff check .` — без ошибок
- [x] 3.2 `ruff format --check .` — без изменений
- [x] 3.3 `pytest` — все тесты зелёные, включая существующие тесты проектов и задач
- [x] 3.4 `alembic upgrade head` на чистой БД: `docker compose down -v && docker compose up -d db`, затем `alembic upgrade head` проходит без ошибок, `alembic revision --autogenerate` не находит изменений схемы (сгенерированный пустой файл удалить)

## Workflow follow-up

- Синхронизировать spec `tasks` в `openspec/specs/` и заархивировать change после ревью.
- Открыть PR из `feat/list-project-tasks` в `main`.
