from typing import Protocol

from devspace_ai.domain.run.models import GenerationRun


class RunRepositoryPort(Protocol):
    def save(self, run: GenerationRun) -> None: ...

    def get(self, run_id: str) -> GenerationRun | None: ...

    def list_recent(self, limit: int = 20) -> list[GenerationRun]: ...
