import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.application.commands import CreateProject, DeleteProject, GetProject
from app.application.use_cases import (
    CreateProjectUseCase,
    DeleteProjectUseCase,
    GetProjectUseCase,
)
from app.presentation.deps import (
    get_create_project_use_case,
    get_delete_project_use_case,
    get_get_project_use_case,
)
from app.presentation.schemas import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectRead)
async def create_project(
    body: ProjectCreate,
    use_case: Annotated[CreateProjectUseCase, Depends(get_create_project_use_case)],
) -> ProjectRead:
    project = await use_case.execute(
        CreateProject(name=body.name, description=body.description)
    )
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    use_case: Annotated[GetProjectUseCase, Depends(get_get_project_use_case)],
) -> ProjectRead:
    project = await use_case.execute(GetProject(project_id=project_id))
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    use_case: Annotated[DeleteProjectUseCase, Depends(get_delete_project_use_case)],
) -> Response:
    await use_case.execute(DeleteProject(project_id=project_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
