from typing import Annotated

from fastapi import Depends, Request

from app.application.ports import UowFactory
from app.application.use_cases import (
    ChangeTaskStatusUseCase,
    CreateProjectUseCase,
    CreateTaskUseCase,
    DeleteProjectUseCase,
    GetProjectUseCase,
    GetTaskUseCase,
    UpdateTaskUseCase,
)


def get_uow_factory(request: Request) -> UowFactory:
    return request.app.state.uow_factory


UowFactoryDep = Annotated[UowFactory, Depends(get_uow_factory)]


def get_create_project_use_case(uow_factory: UowFactoryDep) -> CreateProjectUseCase:
    return CreateProjectUseCase(uow_factory)


def get_get_project_use_case(uow_factory: UowFactoryDep) -> GetProjectUseCase:
    return GetProjectUseCase(uow_factory)


def get_delete_project_use_case(uow_factory: UowFactoryDep) -> DeleteProjectUseCase:
    return DeleteProjectUseCase(uow_factory)


def get_create_task_use_case(uow_factory: UowFactoryDep) -> CreateTaskUseCase:
    return CreateTaskUseCase(uow_factory)


def get_get_task_use_case(uow_factory: UowFactoryDep) -> GetTaskUseCase:
    return GetTaskUseCase(uow_factory)


def get_update_task_use_case(uow_factory: UowFactoryDep) -> UpdateTaskUseCase:
    return UpdateTaskUseCase(uow_factory)


def get_change_task_status_use_case(
    uow_factory: UowFactoryDep,
) -> ChangeTaskStatusUseCase:
    return ChangeTaskStatusUseCase(uow_factory)
