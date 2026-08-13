"""一次生成运行（GenerationRun）的领域表示。

run 是可回查的审计单元：输入文本、产出草稿、校验问题、Graph 步骤轨迹都挂在这里。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from devspace_ai.domain.case_draft.models import CaseDraft
from devspace_ai.domain.style_pack.models import StylePack


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    # 既有合法草稿又有校验问题：部分可用，需人工筛
    PARTIAL = "partial"


@dataclass(frozen=True)
class Issue:
    """结构化问题：既给 API 消费，也回传给模型做一轮 repair。"""

    code: str
    message: str
    draft_index: int | None = None
    field: str | None = None


@dataclass
class StepRecord:
    """Graph 单步执行记录，写入 trace 便于调试耗时与 token。"""

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
    # 便捷字段：取 issues[0].message，便于列表/摘要展示
    error: str | None = None
    style_pack: StylePack | None = None
    # 本次实际调用的适配器/网关模型名；Fake 为 "fake"；旧记录可能为 None
    model: str | None = None

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
