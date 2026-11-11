# Design

## Context

Мотивация — в proposal.md (раздел Why), требования — в `specs/mcp-server/spec.md`.

Что уже есть:
- Все use cases принимают `UowFactory` и бросают только доменные ошибки (`NotFoundError`, `ConflictError`, `DomainValidationError`).
- `app/main.py`: `create_app(settings)` в lifespan создаёт engine и `session_factory` и кладёт `uow_factory` в `app.state`.
- `app/presentation/schemas.py`: `ProjectRead`, `TaskRead`, `TaskPageRead` с `from_attributes=True`.
- `tests/conftest.py`: `settings` на тестовую БД `app_test`, миграции, очистка таблиц перед каждым тестом, `insert_task`.
- FastMCP 4.1.8 (проверено в изолированном окружении): `FastMCP(name, instructions, lifespan=..., mask_error_details=...)`, декораторы `@mcp.tool(annotations=...)` и `@mcp.resource("scheme://{param}")`, доступ к результату lifespan через `Context.lifespan_context`, `ToolError` из `fastmcp.exceptions`, `Client` для тестов в памяти и по stdio, `mcp.run()` по stdio по умолчанию.

## Goals / Non-Goals

**Goals:**
- MCP-сервер вызывает те же use cases, что REST, и не содержит бизнес-логики.
- Ошибки понятны модели: по категории она решает, переспросить пользователя или исправить аргументы.

**Non-Goals:**
- Общий слой «сборки зависимостей» для REST и MCP: пока у них по своей короткой сборке.
- HTTP-транспорт, аутентификация, prompts.

## Decisions

### D1. Фабрика `create_mcp(settings)` с lifespan
`create_mcp(settings: Settings | None = None) -> FastMCP` повторяет `create_app`: lifespan создаёт engine и `session_factory`, отдаёт `uow_factory` и в конце закрывает engine. Инструменты берут фабрику из `ctx.lifespan_context`. Модульная переменная `mcp = create_mcp()` и блок `if __name__ == "__main__": mcp.run()` дают запуск через `python -m`.
Альтернатива — engine на уровне модуля. Отклонена: тесты не смогли бы подменить БД, а соединения не закрывались бы при остановке.

### D2. Инструмент = тонкий адаптер
Каждый инструмент: аргументы → команда или запрос → `use_case.execute()` → схема чтения (`ProjectRead`, `TaskRead`, `TaskPageRead`). FastMCP строит схему параметров из аннотаций, а схему результата — из возвращаемой Pydantic-модели. Параметры:
- id — `uuid.UUID`, enum — `TaskStatus` / `TaskPriority` из домена: недопустимые значения отсекает валидация аргументов FastMCP;
- `limit: Annotated[int, Field(ge=1, le=100)] = 20`, `offset: Annotated[int, Field(ge=0)] = 0`;
- `update_task(task_id, title: str | None = None, priority: TaskPriority | None = None)`.

`delete_project` возвращает `{"deleted": project_id}`, чтобы у модели было подтверждение.
Описание инструмента — docstring функции: что делает, когда вызывать, какие ошибки возможны. Это то, что видит модель.
Альтернатива — свои Pydantic-модели ответа для MCP. Отклонена: схемы чтения уже описывают нужный формат, а оба адаптера живут в presentation.

### D3. Аннотации поведения
`ToolAnnotations`: `readOnlyHint=True` для `get_project`, `get_task`, `list_tasks`; `destructiveHint=True` для `delete_project`; остальным `readOnlyHint=False`. Клиенты (Claude Code, агент) по ним решают, спрашивать ли подтверждение.

### D4. Перевод ошибок
Обёртка вокруг вызова use case ловит `NotFoundError`, `ConflictError`, `DomainValidationError` и бросает `ToolError(f"{category}: {exc}")`. Таблица «класс ошибки → категория» — по образцу `ERROR_STATUS_CODES` в `main.py`. Сервер создаётся с `mask_error_details=True`: текст `ToolError` уходит клиенту, а для прочих исключений клиент получает общую ошибку без стека и SQL.
Альтернатива — возвращать ошибку обычным результатом `{"error": ...}`. Отклонена: клиент и модель не отличат её от успеха, а `isError` в протоколе есть ровно для этого.

### D5. Ресурс `project://{project_id}`
Шаблон ресурса читает проект через `GetProjectUseCase` и задачи через `ListProjectTasksUseCase` с `limit=100`, возвращает JSON `{project, tasks, total}`. Ошибки — через ту же обёртку D4.

### D6. Тесты
- `tests/mcp/conftest.py`: фикстура `mcp_client` — `Client(create_mcp(settings))` в памяти на тестовой БД; очистка таблиц и миграции — из общего `conftest.py`.
- `tests/mcp/test_mcp_server.py`: по тесту на каждый Scenario. Ошибки проверяются через `pytest.raises(ToolError, match="^conflict:")`.
- Smoke-тест stdio: `Client` с stdio-транспортом запускает `python -m app.presentation.mcp_server` с `DATABASE_URL` тестовой БД и получает список инструментов. Помечен маркером `slow`, по умолчанию запускается вместе со всеми.

### D7. Документация
В `CLAUDE.md` в раздел «Команды»: запуск MCP-сервера и подключение к Claude Code (`claude mcp add`). В раздел «Архитектура»: MCP-сервер как второй адаптер presentation.

## Risks / Trade-offs

- [FastMCP быстро меняет API между мажорными версиями] → зависимость ограничена `>=4.1.8,<5`; тесты в памяти поймают поломку при обновлении.
- [Модель получает сырые UUID и может их выдумывать] → в описаниях инструментов сказано брать id только из ответов других инструментов; правило продублируем в системном промпте агента (отдельный change).
- [Smoke-тест stdio запускает процесс и медленнее остальных] → один тест; если станет мешать, его можно исключить маркером.
- [В ресурсе не больше 100 задач] → для больших проектов есть `list_tasks` с пагинацией; ограничение указано в описании ресурса.

## Migration Plan

Схема БД не меняется. Новая зависимость ставится через `uv sync`. Откат — откат кода и зависимости.
