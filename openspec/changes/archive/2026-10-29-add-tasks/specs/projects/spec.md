# Spec Delta

## MODIFIED Requirements

### Requirement: Создание проекта
Система SHALL создавать проект по `POST /projects` с телом `{name, description?}` и возвращать 201 с телом `{id, name, description, created_at}`. Пробелы по краям `name` и `description` MUST обрезаться; пустое или состоящее из пробелов `description` MUST сохраняться как `null`. Тело с неизвестными полями MUST отклоняться с 422, проект при этом не создаётся.

#### Scenario: Успешное создание проекта
- **WHEN** клиент отправляет `POST /projects` с `{"name": "Alpha", "description": "Первый проект"}`
- **THEN** система отвечает 201, в теле есть сгенерированный `id`, `name` = `"Alpha"`, `description` = `"Первый проект"` и `created_at`

#### Scenario: Создание без описания
- **WHEN** клиент отправляет `POST /projects` с `{"name": "Alpha"}`
- **THEN** система отвечает 201 и `description` = `null`

#### Scenario: Обрезка пробелов
- **WHEN** клиент отправляет `POST /projects` с `{"name": "  Alpha  ", "description": "   "}`
- **THEN** система отвечает 201, `name` = `"Alpha"` и `description` = `null`

#### Scenario: Лишнее поле в теле
- **WHEN** клиент отправляет `POST /projects` с `{"name": "Alpha", "owner": "bob"}`
- **THEN** система отвечает 422 и проект не создаётся
