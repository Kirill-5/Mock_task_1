from app.application.commands import (
    ChangeTaskStatus,
    CreateProject,
    CreateTask,
    DeleteProject,
    GetProject,
    GetTask,
    ListProjectTasks,
    TaskPage,
    UpdateTask,
)
from app.application.ports import UowFactory
from app.domain.entities import Project, Task
from app.domain.errors import (
    ProjectHasTasksInProgress,
    ProjectNameAlreadyExists,
    ProjectNotFound,
    TaskNotFound,
    TaskTitleAlreadyExists,
)


class CreateProjectUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: CreateProject) -> Project:
        project = Project.new(command.name, command.description)

        async with self._uow_factory() as uow:
            if await uow.projects.exists_by_name(project.name):
                raise ProjectNameAlreadyExists(
                    f"project with name '{project.name}' already exists"
                )

            await uow.projects.add(project)
            await uow.commit()

            return project


class GetProjectUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: GetProject) -> Project:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(query.project_id)

        if project is None:
            raise ProjectNotFound(f"project {query.project_id} not found")

        return project


class GetTaskUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: GetTask) -> Task:
        async with self._uow_factory() as uow:
            task = await uow.tasks.get(query.task_id)

        if task is None:
            raise TaskNotFound(f"task {query.task_id} not found")

        return task


class DeleteProjectUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: DeleteProject) -> None:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(command.project_id)
            if project is None:
                raise ProjectNotFound(f"project {command.project_id} not found")

            if await uow.tasks.has_tasks_in_progress(project.id):
                raise ProjectHasTasksInProgress(
                    f"project with ID '{project.id}' has tasks in progress"
                )

            await uow.projects.delete(project)
            await uow.commit()


class CreateTaskUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: CreateTask) -> Task:
        task = Task.new(command.project_id, command.title, command.priority)

        async with self._uow_factory() as uow:
            project = await uow.projects.get(command.project_id)
            if project is None:
                raise ProjectNotFound(f"project {command.project_id} not found")

            if await uow.tasks.exists_by_title(task.project_id, task.title):
                raise TaskTitleAlreadyExists(
                    f"task with title '{task.title}' already exists in project {task.project_id}"
                )

            await uow.tasks.add(task)
            await uow.commit()

        return task


class UpdateTaskUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: UpdateTask) -> Task:
        async with self._uow_factory() as uow:
            task = await uow.tasks.get(command.task_id)
            if task is None:
                raise TaskNotFound(f"task {command.task_id} not found")

            old_title = task.title
            task.update(command.title, command.priority)

            title_changed = task.title.casefold() != old_title.casefold()
            if title_changed and await uow.tasks.exists_by_title(
                task.project_id, task.title
            ):
                raise TaskTitleAlreadyExists(
                    f"task with title '{task.title}' already exists in project {task.project_id}"
                )

            await uow.tasks.update(task)
            await uow.commit()

        return task


class ChangeTaskStatusUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, command: ChangeTaskStatus) -> Task:
        async with self._uow_factory() as uow:
            task = await uow.tasks.get(command.task_id)
            if task is None:
                raise TaskNotFound(f"task {command.task_id} not found")

            task.change_status(command.status)

            await uow.tasks.update(task)
            await uow.commit()

        return task


class ListProjectTasksUseCase:
    def __init__(self, uow_factory: UowFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, query: ListProjectTasks) -> TaskPage:
        async with self._uow_factory() as uow:
            project = await uow.projects.get(query.project_id)
            if project is None:
                raise ProjectNotFound(f"project {query.project_id} not found")

            items = await uow.tasks.list_by_project(
                query.project_id,
                status=query.status,
                priority=query.priority,
                limit=query.limit,
                offset=query.offset,
            )
            total = await uow.tasks.count_by_project(
                query.project_id,
                status=query.status,
                priority=query.priority,
            )

        return TaskPage(
            items=items, total=total, limit=query.limit, offset=query.offset
        )
