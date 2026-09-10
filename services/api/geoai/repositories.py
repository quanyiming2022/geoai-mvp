"""P0 contracts only. P1 supplies authenticated, RLS-backed implementations.
Never substitute a service-role client for a user-scoped repository.
"""

from typing import Protocol
from uuid import UUID


class ProjectRepository(Protocol):
    def list_for_user(self, user_id: UUID) -> list[dict]: ...
    def get(self, project_id: UUID, user_id: UUID) -> dict | None: ...


class ProjectResourceRepository(Protocol):
    def list_for_project(self, project_id: UUID, user_id: UUID) -> list[dict]: ...
    def get(self, resource_id: UUID, user_id: UUID) -> dict | None: ...


class RasterRepository(ProjectResourceRepository, Protocol):
    pass


class AoiRepository(ProjectResourceRepository, Protocol):
    pass


class PromptRepository(ProjectResourceRepository, Protocol):
    pass


class JobRepository(ProjectResourceRepository, Protocol):
    pass


class ResultRepository(ProjectResourceRepository, Protocol):
    pass


class ReviewRepository(ProjectResourceRepository, Protocol):
    pass
