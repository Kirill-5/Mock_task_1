# Spec Delta

## Purpose

MCP-интерфейс к проектам и задачам для LLM-агентов: инструменты с описаниями и схемами параметров, ресурс проекта, единый формат ошибок и локальный запуск по stdio. Правила домена те же, что у REST API.

## ADDED Requirements

### Requirement: Набор инструментов
Сервер SHALL предоставлять инструменты `create_project`, `get_project`, `delete_project`, `create_task`, `get_task`, `list_tasks`, `update_task`, `change_task_status`. У каждого инструмента MUST быть описание и схема параметров с типами. Инструменты только для чтения MUST быть помечены как read-only, `delete_project` — как разрушающий.

#### Scenario: Список инструментов
- **WHEN** клиент запрашивает список инструментов
- **THEN** сервер возвращает ровно эти восемь инструментов, у каждого непустое описание и схема параметров

#### Scenario: Подсказки о поведении инструментов
- **WHEN** клиент запрашивает список инструментов
- **THEN** `get_project`, `get_task` и `list_tasks` помечены как read-only, `delete_project` помечен как destructive

### Requirement: Инструменты проектов
`create_project(name, description?)` SHALL создавать проект и возвращать `{id, name, description, created_at}`; `get_project(project_id)` — возвращать проект; `delete_project(project_id)` — удалять проект и возвращать его `id`. Правила валидации, уникальности имени и запрета удаления проекта с задачами в работе MUST быть теми же, что у REST API.

#### Scenario: Создание и получение проекта
- **WHEN** клиент вызывает `create_project` с `name` = `"  Alpha  "`, затем `get_project` с полученным `id`
- **THEN** оба вызова успешны и возвращают проект с `name` = `"Alpha"`

#### Scenario: Повтор имени проекта
- **WHEN** проект `"Alpha"` существует и клиент вызывает `create_project` с `name` = `"alpha"`
- **THEN** вызов завершается ошибкой категории `conflict`, новый проект не создаётся

#### Scenario: Удаление проекта
- **WHEN** проект без задач в работе существует и клиент вызывает `delete_project`
- **THEN** вызов успешен, а последующий `get_project` завершается ошибкой категории `not_found`

#### Scenario: Удаление проекта с задачей в работе
- **WHEN** в проекте есть задача в `in_progress` и клиент вызывает `delete_project`
- **THEN** вызов завершается ошибкой категории `conflict`, проект остаётся

### Requirement: Инструменты задач
`create_task(project_id, title, priority?)`, `get_task(task_id)`, `update_task(task_id, title?, priority?)` и `change_task_status(task_id, status)` SHALL работать по тем же правилам, что соответствующие ручки REST API, и возвращать задачу `{id, project_id, title, priority, status, created_at, updated_at}`.

#### Scenario: Жизненный цикл задачи
- **WHEN** клиент создаёт задачу с `priority` = `"high"`, меняет `title` через `update_task` и переводит её в `in_progress`, затем в `done`
- **THEN** каждый вызов успешен, а `get_task` возвращает новый `title`, `priority` = `"high"` и `status` = `"done"`

#### Scenario: Запрещённый переход статуса
- **WHEN** задача в `todo` и клиент вызывает `change_task_status` с `status` = `"done"`
- **THEN** вызов завершается ошибкой категории `conflict`, статус остаётся `todo`

#### Scenario: Изменение задачи в done
- **WHEN** задача в `done` и клиент вызывает `update_task` с новым `title`
- **THEN** вызов завершается ошибкой категории `conflict`, задача не меняется

#### Scenario: Задача в несуществующем проекте
- **WHEN** клиент вызывает `create_task` со случайным `project_id`
- **THEN** вызов завершается ошибкой категории `not_found`

### Requirement: Список задач через MCP
`list_tasks(project_id, status?, priority?, limit?, offset?)` SHALL возвращать `{items, total, limit, offset}` с теми же фильтрами, пагинацией (`limit` 1–100, по умолчанию 20; `offset` ≥ 0, по умолчанию 0) и сортировкой, что `GET /projects/{id}/tasks`.

#### Scenario: Фильтр и пагинация
- **WHEN** в проекте три задачи с `priority` = `"high"` и одна с `"low"`, и клиент вызывает `list_tasks` с `priority` = `"high"`, `limit` = 2
- **THEN** вызов возвращает две задачи с `priority` = `"high"`, `total` = 3, `limit` = 2, `offset` = 0

#### Scenario: Недопустимый limit
- **WHEN** клиент вызывает `list_tasks` с `limit` = 0 или `limit` = 101
- **THEN** оба вызова завершаются ошибкой, данные не меняются

### Requirement: Формат ошибок инструментов
Доменная ошибка MUST возвращаться клиенту как ошибка инструмента с текстом `<category>: <message>`, где `category` — `not_found`, `conflict` или `validation`. Некорректные аргументы (не UUID, недопустимое значение enum) MUST давать ошибку инструмента. Внутренние ошибки MUST NOT раскрывать детали реализации. После любой ошибки сервер MUST продолжать обслуживать вызовы.

#### Scenario: Ошибка валидации домена
- **WHEN** клиент вызывает `create_task` с `title` = `"ab"`
- **THEN** вызов завершается ошибкой, текст начинается с `validation:`

#### Scenario: Некорректные аргументы
- **WHEN** клиент вызывает `get_task` с `task_id` = `"not-a-uuid"` или `change_task_status` с `status` = `"archived"`
- **THEN** оба вызова завершаются ошибкой инструмента

#### Scenario: Сервер работает после ошибки
- **WHEN** вызов `get_project` со случайным UUID завершился ошибкой `not_found:`
- **THEN** следующий вызов `create_project` с корректными данными успешен

### Requirement: Ресурс проекта
Сервер SHALL предоставлять шаблон ресурса `project://{project_id}`, который возвращает JSON `{project, tasks, total}`: проект и до 100 его задач в порядке списка. Для несуществующего проекта чтение MUST завершаться ошибкой.

#### Scenario: Чтение ресурса проекта
- **WHEN** в проекте две задачи и клиент читает `project://{id}`
- **THEN** клиент получает JSON с проектом, двумя задачами и `total` = 2

#### Scenario: Ресурс несуществующего проекта
- **WHEN** клиент читает `project://{id}` со случайным UUID
- **THEN** чтение завершается ошибкой

### Requirement: Запуск по stdio
Сервер SHALL запускаться командой `python -m app.presentation.mcp_server`, работать по stdio и брать строку подключения к БД из тех же настроек, что REST API (`DATABASE_URL`).

#### Scenario: Подключение по stdio
- **WHEN** MCP-клиент запускает сервер этой командой по stdio с `DATABASE_URL` тестовой БД
- **THEN** клиент проходит инициализацию и получает список из восьми инструментов
