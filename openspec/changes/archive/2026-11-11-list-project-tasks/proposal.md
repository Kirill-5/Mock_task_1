# Proposal

## Why

Задачи можно создавать, получать по одной и менять, но посмотреть все задачи проекта нельзя: `GET /projects/{id}/tasks` из CLAUDE.md не реализован. Команда `ListProjectTasks`, результат `TaskPage` и `ListProjectTasksUseCase` уже написаны, но `SqlAlchemyTaskRepository` не реализует `list_by_project` и `count_by_project`, а HTTP-роута нет. Этот change закрывает последнюю ручку API из CLAUDE.md.

## What Changes

- `SqlAlchemyTaskRepository`: методы `list_by_project` и `count_by_project`. Оба используют одни и те же условия фильтрации по `status` и `priority`. Список отсортирован по `created_at` от новых к старым, при равном `created_at` — по `id`, чтобы страницы не пересекались.
- Presentation: схема ответа страницы `{items, total, limit, offset}`, где `items` — задачи в формате `TaskRead`; зависимость для `ListProjectTasksUseCase`.
- Новый эндпоинт `GET /projects/{id}/tasks` — 200. Query-параметры `status`, `priority` (необязательные), `limit` 1–100 (по умолчанию 20), `offset` ≥ 0 (по умолчанию 0). Невалидные значения дают 422, несуществующий проект — 404.
- Тесты: интеграционные тесты новых методов репозитория и API-тесты, по тесту на каждый Scenario из spec.

## Out of Scope

- Сортировка по другим полям и выбор направления сортировки клиентом.
- Поиск по `title` и фильтры по датам.
- Курсорная пагинация (`cursor`/`next`): только `limit`/`offset`.
- Отклонение неизвестных query-параметров: FastAPI их игнорирует, это поведение сохраняется.
- Изменения схемы БД и новые миграции: индекс `ix_tasks_project_id_created_at` уже есть в первой миграции.
- Изменения домена, команд и `ListProjectTasksUseCase`: они уже соответствуют требованиям.
- Docker-образ API и README: отдельный шаг.

## Capabilities

### New Capabilities

(нет)

### Modified Capabilities
- `tasks`: новое требование «Список задач проекта» — фильтры, пагинация, сортировка, формат ответа, ошибки 404 и 422.

## Impact

- **Код:**
  - `app/infrastructure/db/repository.py`: `list_by_project`, `count_by_project` в `SqlAlchemyTaskRepository`;
  - `app/presentation/schemas.py`: схема страницы задач;
  - `app/presentation/deps.py`: зависимость для `ListProjectTasksUseCase`;
  - `app/presentation/routers/tasks.py`: роут `GET /projects/{project_id}/tasks`.
- **API:** новый эндпоинт `GET /projects/{id}/tasks`. Существующие эндпоинты не меняются.
- **БД:** без изменений.
- **Зависимости:** без изменений.
