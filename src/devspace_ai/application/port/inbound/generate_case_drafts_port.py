from typing import Protocol

from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.dto.results import GenerateCaseDraftsResult


class GenerateCaseDraftsPort(Protocol):
    async def generate(self, command: GenerateCaseDraftsCommand) -> GenerateCaseDraftsResult: ...
