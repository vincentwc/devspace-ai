"""入站端口：生成用例草稿用例接口（由 CaseGenerationService 实现）。"""

from typing import Protocol

from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.dto.results import GenerateCaseDraftsResult


class GenerateCaseDraftsPort(Protocol):
    async def generate(self, command: GenerateCaseDraftsCommand) -> GenerateCaseDraftsResult: ...
