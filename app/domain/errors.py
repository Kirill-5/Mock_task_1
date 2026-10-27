class DomainError(Exception):
    """Базовая ошибка предметной области."""


class DomainValidationError(DomainError):
    """Данные не прошли проверку: длина, формат, допустимые значения (422)."""


class NotFoundError(DomainError):
    """Запрошенный объект не найден (404)."""


class ProjectNotFound(NotFoundError):
    """Проект не найден."""


class TaskNotFound(NotFoundError):
    """Задача не найдена."""


class ConflictError(DomainError):
    """Действие противоречит правилам или текущему состоянию данных (409)."""


class ProjectNameAlreadyExists(ConflictError):
    """Проект с таким именем уже существует."""


class TaskTitleAlreadyExists(ConflictError):
    """В проекте уже есть задача с таким title."""


class InvalidStatusTransition(ConflictError):
    """Запрещённый переход статуса задачи."""


class TaskAlreadyDone(ConflictError):
    """Задачу в статусе done нельзя изменять."""


class ProjectHasTasksInProgress(ConflictError):
    """Нельзя удалить проект, пока в нём есть задачи в работе."""
