# Spec Delta

## Purpose

Управление задачами проекта через REST API: создание задачи в проекте, получение, изменение `title` и `priority` и смена статуса по разрешённым переходам с соблюдением правил валидации и уникальности `title` внутри проекта.

## ADDED Requirements

### Requirement: Создание задачи
Система SHALL создавать задачу по `POST /projects/{id}/tasks` с телом `{title, priority?}` и возвращать 201 с телом `{id, project_id, title, priority, status, created_at, updated_at}`. Пробелы по краям `title` MUST обрезаться. `priority` по умолчанию MUST быть `medium`, `status` новой задачи MUST всегда быть `todo`. Тело с неизвестными полями (в том числе `status`) MUST отклоняться с 422.

#### Scenario: Успешное создание задачи
- **WHEN** проект существует и клиент отправляет `POST /projects/{id}/tasks` с `{"title": "Write spec", "priority": "high"}`
- **THEN** система отвечает 201, в теле есть сгенерированный `id`, `project_id` равен id проекта, `title` = `"Write spec"`, `priority` = `"high"`, `status` = `"todo"`, `created_at` и `updated_at`

#### Scenario: Приоритет по умолчанию
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{"title": "Write spec"}`
- **THEN** система отвечает 201 и `priority` = `"medium"`

#### Scenario: Обрезка пробелов в title
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{"title": "  Write spec  "}`
- **THEN** система отвечает 201 и `title` = `"Write spec"`

#### Scenario: Статус при создании задать нельзя
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{"title": "Write spec", "status": "done"}`
- **THEN** система отвечает 422 и задача не создаётся

### Requirement: Создание задачи в несуществующем проекте
Система MUST отвечать 404 на `POST /projects/{id}/tasks` с корректным `title`, если проекта с таким `id` нет, и 422, если `id` не является UUID. Задача при этом MUST NOT создаваться.

#### Scenario: Проект не найден
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{"title": "Write spec"}` и случайным UUID, которого нет в системе
- **THEN** система отвечает 404 и задача не создаётся

#### Scenario: Некорректный идентификатор проекта
- **WHEN** клиент отправляет `POST /projects/not-a-uuid/tasks` с `{"title": "Write spec"}`
- **THEN** система отвечает 422

### Requirement: Валидация title задачи
Система MUST отклонять создание и изменение задачи с ответом 422, если `title` после обрезки пробелов короче 3 или длиннее 200 символов или не является строкой. При создании `title` обязателен. Задача при этом MUST NOT создаваться или меняться.

#### Scenario: Слишком короткий title
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{"title": "ab"}`
- **THEN** система отвечает 422 и задача не создаётся

#### Scenario: Title короче 3 символов после обрезки пробелов
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{"title": "  ab  "}`
- **THEN** система отвечает 422

#### Scenario: Слишком длинный title
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `title` длиной 201 символ
- **THEN** система отвечает 422

#### Scenario: Граничные длины title
- **WHEN** клиент создаёт задачи с `title` длиной 3 и 200 символов
- **THEN** система отвечает 201 на оба запроса

#### Scenario: Title не передан
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{}`
- **THEN** система отвечает 422

#### Scenario: Некорректный title при изменении
- **WHEN** задача в `todo` существует и клиент отправляет `PATCH /tasks/{id}` с `{"title": "ab"}`
- **THEN** система отвечает 422 и `GET /tasks/{id}` возвращает прежний `title`

### Requirement: Валидация priority задачи
Система MUST отклонять создание и изменение задачи с ответом 422, если `priority` не одно из `low`, `medium`, `high`.

#### Scenario: Недопустимый priority при создании
- **WHEN** клиент отправляет `POST /projects/{id}/tasks` с `{"title": "Write spec", "priority": "urgent"}`
- **THEN** система отвечает 422 и задача не создаётся

#### Scenario: Недопустимый priority при изменении
- **WHEN** задача в `todo` существует и клиент отправляет `PATCH /tasks/{id}` с `{"priority": "urgent"}`
- **THEN** система отвечает 422 и `GET /tasks/{id}` возвращает прежний `priority`

### Requirement: Уникальность title внутри проекта
`title` задачи MUST быть уникальным внутри проекта без учёта регистра (сравнение после обрезки пробелов) при создании и при изменении. Нарушение MUST завершаться ответом 409, существующие задачи при этом не меняются. В разных проектах одинаковые `title` MUST допускаться.

#### Scenario: Повтор title в другом регистре
- **WHEN** в проекте есть задача `"Write spec"` и клиент отправляет `POST /projects/{id}/tasks` с `{"title": "  WRITE SPEC "}`
- **THEN** система отвечает 409

#### Scenario: Одинаковый title в разных проектах
- **WHEN** в проекте A есть задача `"Write spec"` и клиент создаёт задачу `"Write spec"` в проекте B
- **THEN** система отвечает 201

#### Scenario: Изменение title на занятый
- **WHEN** в проекте есть задачи `"Write spec"` и `"Review spec"` и клиент отправляет `PATCH` второй задачи с `{"title": "write spec"}`
- **THEN** система отвечает 409 и вторая задача сохраняет `title` = `"Review spec"`

#### Scenario: Изменение регистра собственного title
- **WHEN** задача `"Write spec"` существует и клиент отправляет `PATCH /tasks/{id}` с `{"title": "WRITE SPEC"}`
- **THEN** система отвечает 200 и `title` = `"WRITE SPEC"`

#### Scenario: Уникальность гарантируется на уровне хранилища
- **WHEN** в хранилище напрямую, минуя проверку уникальности, записываются две задачи одного проекта с `title`, отличающимися только регистром
- **THEN** вторая запись отклоняется хранилищем

### Requirement: Получение задачи
Система SHALL возвращать задачу по `GET /tasks/{id}` с ответом 200 и телом `{id, project_id, title, priority, status, created_at, updated_at}`. Для несуществующего `id` MUST возвращаться 404, для `id`, не являющегося UUID, — 422.

#### Scenario: Получение существующей задачи
- **WHEN** задача создана и клиент отправляет `GET /tasks/{id}`
- **THEN** система отвечает 200 и тело совпадает с ответом на создание

#### Scenario: Задача не найдена
- **WHEN** клиент отправляет `GET /tasks/{id}` со случайным UUID, которого нет в системе
- **THEN** система отвечает 404

#### Scenario: Некорректный идентификатор задачи
- **WHEN** клиент отправляет `GET /tasks/not-a-uuid`
- **THEN** система отвечает 422

### Requirement: Изменение задачи
Система SHALL менять `title` и/или `priority` задачи по `PATCH /tasks/{id}` и возвращать 200 с полным телом задачи. Непереданные поля MUST оставаться без изменений, `updated_at` MUST обновляться. Запрос без `title` и `priority` или с неизвестными полями MUST отклоняться с 422. Для несуществующего `id` — 404, для не-UUID — 422.

#### Scenario: Изменение title
- **WHEN** задача `"Write spec"` с `priority` = `"low"` существует и клиент отправляет `PATCH /tasks/{id}` с `{"title": "  Write tests "}`
- **THEN** система отвечает 200, `title` = `"Write tests"`, `priority` = `"low"`, `updated_at` больше прежнего

#### Scenario: Изменение priority
- **WHEN** задача с `priority` = `"medium"` существует и клиент отправляет `PATCH /tasks/{id}` с `{"priority": "high"}`
- **THEN** система отвечает 200, `priority` = `"high"`, `title` не изменился

#### Scenario: Изменение title и priority одновременно
- **WHEN** клиент отправляет `PATCH /tasks/{id}` с `{"title": "Write tests", "priority": "low"}`
- **THEN** система отвечает 200 и оба поля изменены

#### Scenario: Пустое изменение
- **WHEN** задача в `todo` существует и клиент отправляет `PATCH /tasks/{id}` с `{}` или `{"title": null, "priority": null}`
- **THEN** система отвечает 422 и задача, включая `updated_at`, не меняется

#### Scenario: Попытка сменить статус через PATCH
- **WHEN** задача в `todo` существует и клиент отправляет `PATCH /tasks/{id}` с `{"status": "done"}`
- **THEN** система отвечает 422, `status` и `updated_at` задачи не меняются

#### Scenario: Изменение несуществующей задачи
- **WHEN** клиент отправляет `PATCH /tasks/{id}` с `{"priority": "high"}` и случайным UUID
- **THEN** система отвечает 404

#### Scenario: Изменение с некорректным идентификатором
- **WHEN** клиент отправляет `PATCH /tasks/not-a-uuid` с `{"priority": "high"}`
- **THEN** система отвечает 422

### Requirement: Запрет изменения задачи в done
Система MUST отклонять `PATCH /tasks/{id}` с ответом 409, если задача в статусе `done` и тело корректно по форме. Ошибки формы тела (недопустимое значение `priority`, не-строковый `title`, неизвестные поля) MUST давать 422 раньше проверки `done`; ошибки длины `title` проверяются после неё и дают 409. Задача MUST остаться без изменений.

#### Scenario: Изменение задачи в done
- **WHEN** задача в `done` существует и клиент отправляет `PATCH /tasks/{id}` с `{"title": "New title"}`
- **THEN** система отвечает 409 и `GET /tasks/{id}` возвращает прежние `title` и `updated_at`

#### Scenario: Пустое изменение задачи в done
- **WHEN** задача в `done` существует и клиент отправляет `PATCH /tasks/{id}` с `{}`
- **THEN** система отвечает 409

#### Scenario: Ошибка формы тела у задачи в done
- **WHEN** задача в `done` существует и клиент отправляет `PATCH /tasks/{id}` с `{"priority": "urgent"}` или с `{"title": "New title", "status": "todo"}`
- **THEN** система отвечает 422 на оба запроса и задача не меняется

#### Scenario: Некорректная длина title у задачи в done
- **WHEN** задача в `done` существует и клиент отправляет `PATCH /tasks/{id}` с `{"title": "ab"}`
- **THEN** система отвечает 409

### Requirement: Смена статуса задачи
Система SHALL менять статус по `POST /tasks/{id}/status` с телом `{status}` и возвращать 200 с полным телом задачи и обновлённым `updated_at`. Разрешены только переходы `todo → in_progress`, `in_progress → done`, `in_progress → todo`. Тело с неизвестными полями MUST отклоняться с 422.

#### Scenario: Взять задачу в работу
- **WHEN** задача в `todo` и клиент отправляет `POST /tasks/{id}/status` с `{"status": "in_progress"}`
- **THEN** система отвечает 200, `status` = `"in_progress"`, `updated_at` больше прежнего

#### Scenario: Завершить задачу
- **WHEN** задача в `in_progress` и клиент отправляет `POST /tasks/{id}/status` с `{"status": "done"}`
- **THEN** система отвечает 200 и `status` = `"done"`

#### Scenario: Вернуть задачу в todo
- **WHEN** задача в `in_progress` и клиент отправляет `POST /tasks/{id}/status` с `{"status": "todo"}`
- **THEN** система отвечает 200 и `status` = `"todo"`

#### Scenario: Лишнее поле при смене статуса
- **WHEN** задача в `todo` и клиент отправляет `POST /tasks/{id}/status` с `{"status": "in_progress", "title": "X"}`
- **THEN** система отвечает 422 и статус остаётся `todo`

### Requirement: Запрещённые переходы статуса
Система MUST отклонять с ответом 409 любой переход статуса, кроме разрешённых, включая переход в текущий статус и любой переход из `done`. Недопустимое значение `status` или его отсутствие MUST давать 422; для несуществующей задачи — 404, для не-UUID — 422.

#### Scenario: Пропуск in_progress
- **WHEN** задача в `todo` и клиент отправляет `POST /tasks/{id}/status` с `{"status": "done"}`
- **THEN** система отвечает 409 и статус остаётся `todo`

#### Scenario: Переход в текущий статус
- **WHEN** задача в `todo` и клиент отправляет `POST /tasks/{id}/status` с `{"status": "todo"}`
- **THEN** система отвечает 409

#### Scenario: Переход из done
- **WHEN** задача в `done` и клиент отправляет `POST /tasks/{id}/status` с `{"status": "in_progress"}` или `{"status": "todo"}`
- **THEN** система отвечает 409 на оба запроса и статус остаётся `done`

#### Scenario: Недопустимое значение статуса
- **WHEN** клиент отправляет `POST /tasks/{id}/status` с `{"status": "archived"}` или с `{}`
- **THEN** система отвечает 422

#### Scenario: Смена статуса несуществующей задачи
- **WHEN** клиент отправляет `POST /tasks/{id}/status` с `{"status": "in_progress"}` и случайным UUID
- **THEN** система отвечает 404

#### Scenario: Смена статуса с некорректным идентификатором
- **WHEN** клиент отправляет `POST /tasks/not-a-uuid/status` с `{"status": "in_progress"}`
- **THEN** система отвечает 422
