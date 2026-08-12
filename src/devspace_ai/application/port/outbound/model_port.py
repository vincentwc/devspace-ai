from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelGenerationResult:
    raw_drafts: list[dict]
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ModelPort(Protocol):
    async def generate_case_drafts(
        self,
        requirement_text: str,
        *,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        repair_issues: list[str] | None,
    ) -> ModelGenerationResult: ...
