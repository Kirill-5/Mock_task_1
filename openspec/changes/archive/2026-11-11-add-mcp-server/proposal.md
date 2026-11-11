# Proposal

## Why

Сейчас с проектами и задачами можно работать только через REST API. Следующий шаг — LLM-агент, который выполняет запросы пользователя на естественном языке, а агентам нужен MCP-интерфейс: инструменты с описаниями и схемами параметров. MCP-сервер — ещё один presentation-слой поверх тех же use cases, поэтому домен, application и хранилище не меняются.

## What Changes

- Новая зависимость `fastmcp`.
- MCP-сервер `app/presentation/mcp_server.py` с инструментами:
  - проекты: `create_project`, `get_project`, `delete_project`;
  - задачи: `create_task`, `get_task`, `list_tasks`, `update_task`, `change_task_status`.
- Ресурс `project://{project_id}`: проект и его задачи только для чтения.
- Доменные ошибки возвращаются клиенту как ошибки инструмента с категорией (`not_found`, `conflict`, `validation`) и текстом. Внутренние ошибки скрываются.
- Запуск по stdio командой `python -m app.presentation.mcp_server`; команда и подключение к Claude Code описаны в `CLAUDE.md`.
- Тесты инструментов и ресурса через клиент FastMCP в памяти и smoke-тест запуска по stdio.

## Out of Scope

- LLM-агент на LangChain и RAG: отдельные change.
- HTTP-транспорт MCP и аутентификация: сервер запускается локально по stdio.
- MCP prompts и sampling.
- Изменения домена, use cases, репозиториев, схемы БД и REST API.
- Docker-образ и README: отдельный шаг.

## Capabilities

### New Capabilities
- `mcp-server`: MCP-интерфейс к проектам и задачам — набор инструментов, ресурс проекта, формат ошибок и запуск по stdio.

### Modified Capabilities

(нет)

## Impact

- **Код:** новый `app/presentation/mcp_server.py`; переиспользуются use cases, команды, `SqlAlchemyUnitOfWork` и схемы чтения `ProjectRead`, `TaskRead`, `TaskPageRead`.
- **Зависимости:** `fastmcp` в основных зависимостях `pyproject.toml`.
- **Документация:** команды запуска и подключения MCP-сервера в `CLAUDE.md`.
- **API и БД:** без изменений.
