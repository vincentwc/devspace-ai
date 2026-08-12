from datetime import UTC, datetime

from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.run.models import (
    GenerationRun,
    Issue,
    RunStatus,
    RunTrace,
    StepRecord,
)
from devspace_ai.domain.run.status import resolve_status


def test_status_rules():
    assert resolve_status(valid_count=3, issue_count=0) == RunStatus.SUCCEEDED
    assert resolve_status(valid_count=2, issue_count=1) == RunStatus.PARTIAL
    assert resolve_status(valid_count=0, issue_count=1) == RunStatus.FAILED
    assert resolve_status(valid_count=0, issue_count=0) == RunStatus.FAILED


def test_run_status_has_no_queued():
    values = {s.value for s in RunStatus}
    assert values == {"running", "succeeded", "failed", "partial"}
    assert not hasattr(RunStatus, "QUEUED")


def test_generation_run_start_and_finish():
    run = GenerationRun.start("需求文本")
    assert run.status == RunStatus.RUNNING
    assert run.input_text == "需求文本"
    assert run.run_id
    assert run.drafts == []
    assert run.issues == []
    assert isinstance(run.trace, RunTrace)
    assert run.trace.steps == []

    draft = CaseDraft(
        title="登录成功",
        steps=[TestStep(action="输入账号", expected="进入首页")],
    )
    issue = Issue(code="DRAFT_VALIDATION_FAILED", message="缺步骤", draft_index=1, field="steps")
    run.finish(RunStatus.PARTIAL, drafts=[draft], issues=[issue])

    assert run.status == RunStatus.PARTIAL
    assert run.drafts == [draft]
    assert run.issues == [issue]
    assert run.error == issue.message


def test_step_record_and_trace():
    started = datetime(2026, 8, 12, 6, 0, tzinfo=UTC)
    ended = datetime(2026, 8, 12, 6, 1, tzinfo=UTC)
    step = StepRecord(
        step_name="generate_cases",
        status="succeeded",
        started_at=started,
        ended_at=ended,
        summary="生成 2 条",
        error=None,
        prompt_tokens=10,
        completion_tokens=20,
    )
    trace = RunTrace(steps=[step])
    assert trace.steps[0].step_name == "generate_cases"
    assert trace.steps[0].prompt_tokens == 10
