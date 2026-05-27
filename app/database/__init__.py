from .projects_repository import ProjectsRepository
from .semaphore import ProcessSemaphore, get_process_semaphore

_repository_instance: ProjectsRepository | None = None


def get_projects_repository() -> ProjectsRepository:
    """
    Retorna una instancia singleton del repositorio de proyectos.
    La instancia se crea en la primera llamada.
    """
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = ProjectsRepository()
    return _repository_instance


__all__ = ['ProjectsRepository', 'ProcessSemaphore', 'get_projects_repository', 'get_process_semaphore']