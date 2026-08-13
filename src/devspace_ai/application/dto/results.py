"""应用层出站结果：供 REST/Debug UI 映射为 DTO。"""

from dataclasses import dataclass

from devspace_ai.domain.case_draft.models import CaseDraft
from devspace_ai.domain.run.models import Issue, RunStatus, RunTrace
from devspace_ai.domain.style_pack.models import StylePack


@dataclass
class GenerateCaseDraftsResult:
    run_id: str
    status: RunStatus
    drafts: list[CaseDraft]
    issues: list[Issue]
    trace: RunTrace
    error: str | None
    style_pack: StylePack | None = None
    model: str | None = None
