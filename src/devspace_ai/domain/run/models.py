from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from devspace_ai.domain.case_draft.models import CaseDraft


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    draft_index: int | None = None
    field: str | None = None


@dataclass
class StepRecord:
    step_name: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = None
    error: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class RunTrace:
    steps: list[StepRecord] = field(default_factory=list)


@dataclass
class GenerationRun:
    run_id: str
    status: RunStatus
    input_text: str
    drafts: list[CaseDraft] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    trace: RunTrace = field(default_factory=RunTrace)
    error: str | None = None

    @classmethod
    def start(cls, input_text: str) -> GenerationRun:
        return cls(
            run_id=str(uuid4()),
            status=RunStatus.RUNNING,
            input_text=input_text,
        )

    def finish(
        self,
        status: RunStatus,
        drafts: list[CaseDraft],
        issues: list[Issue],
    ) -> None:
        self.status = status
        self.drafts = list(drafts)
        self.issues = list(issues)
        self.error = issues[0].message if issues else None
