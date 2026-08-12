from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from devspace_ai.application.dto.results import GenerateCaseDraftsResult
from devspace_ai.domain.case_draft.models import CaseDraft
from devspace_ai.domain.run.models import GenerationRun, Issue, RunTrace, StepRecord


class IssueDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    draft_index: int | None = None
    field: str | None = None


class TestStepDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    expected: str
    test_data: str | None = None


class CaseDraftDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    preconditions: list[str]
    steps: list[TestStepDTO]
    priority: str | None = None
    tags: list[str] = []
    rationale: str | None = None


class StepRecordDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_name: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = None
    error: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class RunTraceDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[StepRecordDTO]


class GenerationRunDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: str
    drafts: list[CaseDraftDTO]
    issues: list[IssueDTO]
    trace: RunTraceDTO
    error: str | None = None


def issue_to_dto(issue: Issue) -> IssueDTO:
    return IssueDTO(
        code=issue.code,
        message=issue.message,
        draft_index=issue.draft_index,
        field=issue.field,
    )


def draft_to_dto(draft: CaseDraft) -> CaseDraftDTO:
    return CaseDraftDTO(
        title=draft.title,
        preconditions=list(draft.preconditions),
        steps=[
            TestStepDTO(action=s.action, expected=s.expected, test_data=s.test_data)
            for s in draft.steps
        ],
        priority=draft.priority,
        tags=list(draft.tags),
        rationale=draft.rationale,
    )


def step_to_dto(step: StepRecord) -> StepRecordDTO:
    return StepRecordDTO(
        step_name=step.step_name,
        status=step.status,
        started_at=step.started_at,
        ended_at=step.ended_at,
        summary=step.summary,
        error=step.error,
        prompt_tokens=step.prompt_tokens,
        completion_tokens=step.completion_tokens,
    )


def trace_to_dto(trace: RunTrace) -> RunTraceDTO:
    return RunTraceDTO(steps=[step_to_dto(s) for s in trace.steps])


def result_to_dto(result: GenerateCaseDraftsResult) -> GenerationRunDTO:
    return GenerationRunDTO(
        run_id=result.run_id,
        status=result.status.value,
        drafts=[draft_to_dto(d) for d in result.drafts],
        issues=[issue_to_dto(i) for i in result.issues],
        trace=trace_to_dto(result.trace),
        error=result.error,
    )


def run_to_dto(run: GenerationRun) -> GenerationRunDTO:
    return GenerationRunDTO(
        run_id=run.run_id,
        status=run.status.value,
        drafts=[draft_to_dto(d) for d in run.drafts],
        issues=[issue_to_dto(i) for i in run.issues],
        trace=trace_to_dto(run.trace),
        error=run.error,
    )
