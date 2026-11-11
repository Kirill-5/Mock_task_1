# Spec Delta

## ADDED Requirements

### Requirement: Список задач проекта
Система SHALL возвращать задачи проекта по `GET /projects/{id}/tasks` с ответом 200 и телом `{items, total, limit, offset}`. Каждый элемент `items` MUST иметь формат `{id, project_id, title, priority, status, created_at, updated_at}`. В список MUST попадать только задачи этого проекта. Если задач нет, ответ MUST быть 200 с пустым `items` и `total` = 0.

#### Scenario: Список задач проекта
- **WHEN** в проекте A три задачи, в проекте B одна, и клиент отправляет `GET /projects/{A}/tasks`
- **THEN** система отвечает 200, `items` содержит три задачи проекта A в формате задачи, `total` = 3, `limit` = 20, `offset` = 0

#### Scenario: Проект без задач
- **WHEN** проект существует, задач в нём нет, и клиент отправляет `GET /projects/{id}/tasks`
- **THEN** система отвечает 200 с `{"items": [], "total": 0, "limit": 20, "offset": 0}`

### Requirement: Сортировка списка задач
Задачи в `items` MUST быть упорядочены по `created_at` от новых к старым. При равном `created_at` порядок MUST быть стабильным между запросами, чтобы соседние страницы не пересекались и не теряли задачи.

#### Scenario: Новые задачи первыми
- **WHEN** в проекте созданы задачи `"First"`, `"Second"`, `"Third"` в этом порядке и клиент отправляет `GET /projects/{id}/tasks`
- **THEN** `items` идут в порядке `"Third"`, `"Second"`, `"First"`

#### Scenario: Стабильный порядок при одинаковом created_at
- **WHEN** у пяти задач проекта одинаковый `created_at` и клиент запрашивает страницы `limit=2` с `offset` 0, 2 и 4
- **THEN** страницы вместе содержат все пять задач ровно по одному разу, а повтор тех же запросов возвращает тот же порядок

### Requirement: Фильтрация списка задач
Система MUST фильтровать список по необязательным query-параметрам `status` (`todo`, `in_progress`, `done`) и `priority` (`low`, `medium`, `high`). Оба фильтра вместе MUST применяться одновременно. `total` MUST считаться с учётом фильтров. Недопустимое значение фильтра MUST давать 422.

#### Scenario: Фильтр по статусу
- **WHEN** в проекте задачи в `todo`, `in_progress` и `done` и клиент отправляет `GET /projects/{id}/tasks?status=in_progress`
- **THEN** система отвечает 200, `items` содержит только задачи в `in_progress`, `total` равен их числу

#### Scenario: Фильтр по приоритету
- **WHEN** в проекте задачи с приоритетами `low`, `medium` и `high` и клиент отправляет `GET /projects/{id}/tasks?priority=high`
- **THEN** система отвечает 200, `items` содержит только задачи с `priority` = `"high"`, `total` равен их числу

#### Scenario: Оба фильтра вместе
- **WHEN** в проекте есть задача `high` в `todo`, задача `high` в `in_progress` и задача `low` в `todo`, и клиент отправляет `GET /projects/{id}/tasks?status=todo&priority=high`
- **THEN** система отвечает 200, в `items` одна задача — `high` в `todo`, `total` = 1

#### Scenario: Недопустимое значение фильтра
- **WHEN** клиент отправляет `GET /projects/{id}/tasks?status=archived` или `GET /projects/{id}/tasks?priority=urgent`
- **THEN** система отвечает 422 на оба запроса

### Requirement: Пагинация списка задач
Система MUST поддерживать query-параметры `limit` (целое от 1 до 100, по умолчанию 20) и `offset` (целое ≥ 0, по умолчанию 0) и возвращать их в ответе. `items` MUST содержать не больше `limit` задач, начиная с позиции `offset`. `total` MUST быть числом всех подходящих задач без учёта `limit` и `offset`. Значения вне диапазона или не целые MUST давать 422.

#### Scenario: Страница задач
- **WHEN** в проекте 5 задач и клиент отправляет `GET /projects/{id}/tasks?limit=2&offset=2`
- **THEN** система отвечает 200, `items` содержит 3-ю и 4-ю задачи в порядке сортировки, `total` = 5, `limit` = 2, `offset` = 2

#### Scenario: Offset за пределами списка
- **WHEN** в проекте 3 задачи и клиент отправляет `GET /projects/{id}/tasks?offset=10`
- **THEN** система отвечает 200, `items` пустой, `total` = 3

#### Scenario: Граничные значения limit
- **WHEN** клиент отправляет `GET /projects/{id}/tasks?limit=1` и `GET /projects/{id}/tasks?limit=100`
- **THEN** система отвечает 200 на оба запроса

#### Scenario: Недопустимые limit и offset
- **WHEN** клиент отправляет `GET /projects/{id}/tasks` с `limit=0`, `limit=101`, `limit=abc` или `offset=-1`
- **THEN** система отвечает 422 на каждый запрос

### Requirement: Список задач несуществующего проекта
Система MUST отвечать 404 на `GET /projects/{id}/tasks`, если проекта с таким `id` нет, и 422, если `id` не является UUID.

#### Scenario: Проект не найден
- **WHEN** клиент отправляет `GET /projects/{id}/tasks` со случайным UUID, которого нет в системе
- **THEN** система отвечает 404

#### Scenario: Некорректный идентификатор проекта
- **WHEN** клиент отправляет `GET /projects/not-a-uuid/tasks`
- **THEN** система отвечает 422
