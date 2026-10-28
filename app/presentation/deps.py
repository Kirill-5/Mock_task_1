from typing import Annotated

from fastapi import Depends, Request

from app.application.ports import UowFactory
from app.application.use_cases import (
    CreateProjectUseCase,
    DeleteProjectUseCase,
    GetProjectUseCase,
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
