from dataclasses import dataclass

from devspace_ai.domain.case_draft.models import CaseDraft
from devspace_ai.domain.run.models import Issue, RunStatus, RunTrace


@dataclass
class GenerateCaseDraftsResult:
    run_id: str
    status: RunStatus
    drafts: list[CaseDraft]
    issues: list[Issue]
    trace: RunTrace
    error: str | None
