"""用例草稿生成应用服务：固定 Graph 编排。

流程（同步一次请求内完成）：
  ingest_requirement → generate_cases → validate_cases（必要时带 issues 重试一次）→ persist

本服务只产出草稿与运行记录；业务系统在人工确认后再落库到自己的用例库。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.dto.results import GenerateCaseDraftsResult
from devspace_ai.application.port.outbound.model_port import ModelPort
from devspace_ai.application.port.outbound.run_repository_port import RunRepositoryPort
from devspace_ai.domain.case_draft.errors import CaseDraftValidationError
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.run.models import GenerationRun, Issue, RunStatus, StepRecord
from devspace_ai.domain.run.status import resolve_status
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.source.text_ingest import ingest_text, ingest_upload


class CaseGenerationService:
    """用例草稿生成用例（use case）入口，依赖 Model / Run 两个出站端口。"""

    def __init__(self, settings: Settings, model: ModelPort, runs: RunRepositoryPort) -> None:
        self.settings = settings
        self.model = model
        self.runs = runs

    async def generate(self, command: GenerateCaseDraftsCommand) -> GenerateCaseDraftsResult:
        # text / file 二选一；两者都给或都不给都视为非法输入
        has_text = command.text is not None and str(command.text).strip() != ""
        has_file = command.file_bytes is not None
        if has_text == has_file:
            raise InputRejectedError("INVALID_INPUT", "请只提供文本或文件其中一种")

        if command.max_cases is None:
            max_cases = self.settings.default_max_cases
        else:
            max_cases = command.max_cases
        # hard_max_cases 是服务端硬上限，防止一次请求打爆模型配额
        if max_cases > self.settings.hard_max_cases:
            raise InputRejectedError(
                "MAX_CASES_EXCEEDED",
                f"用例数量上限 {max_cases} 超出硬限制 {self.settings.hard_max_cases}",
            )
        if max_cases < 1:
            raise InputRejectedError("INVALID_INPUT", "用例数量上限必须大于等于 1")

        if has_file:
            doc = ingest_upload(
                command.file_name or "upload.txt",
                command.file_bytes or b"",
                max_bytes=self.settings.max_upload_bytes,
                max_chars=self.settings.max_text_chars,
            )
        else:
            doc = ingest_text(command.text or "", max_chars=self.settings.max_text_chars)

        run = GenerationRun.start(doc.text)
        t0 = datetime.now(UTC)
        run.trace.steps.append(
            StepRecord(
                "ingest_requirement",
                "succeeded",
                t0,
                datetime.now(UTC),
                summary=f"chars={len(doc.text)}",
            )
        )

        try:
            # 整段生成+校验受 total_timeout 约束（含一次 repair 重试）
            drafts, issues = await asyncio.wait_for(
                self._generate_and_validate(
                    doc.text, max_cases, command.language, command.domain_hint, run
                ),
                timeout=self.settings.total_timeout_seconds,
            )
            status = resolve_status(len(drafts), len(issues))
            run.finish(status, drafts, issues)
        except (TimeoutError, httpx.TimeoutException):
            # asyncio 超时与 httpx 单次调用超时统一映射为 MODEL_TIMEOUT
            run.finish(
                RunStatus.FAILED,
                [],
                [Issue("MODEL_TIMEOUT", "模型调用或整次请求超时")],
            )
            run.trace.steps.append(
                StepRecord(
                    "generate_cases",
                    "failed",
                    datetime.now(UTC),
                    datetime.now(UTC),
                    error="超时",
                )
            )
        except Exception as exc:
            # 未预期异常也落库，便于调试页/GET run 回看
            run.finish(
                RunStatus.FAILED,
                [],
                [Issue("INTERNAL_ERROR", str(exc) or type(exc).__name__)],
            )
            run.trace.steps.append(
                StepRecord(
                    "generate_cases",
                    "failed",
                    datetime.now(UTC),
                    datetime.now(UTC),
                    error=type(exc).__name__,
                )
            )
        # 无论成功失败都持久化，API 可按 run_id 回查
        self.runs.save(run)
        return GenerateCaseDraftsResult(
            run.run_id, run.status, run.drafts, run.issues, run.trace, run.error
        )

    async def _generate_and_validate(
        self,
        text: str,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        run: GenerationRun,
    ) -> tuple[list[CaseDraft], list[Issue]]:
        """调用模型并做结构校验；若有校验问题则带 issues 再生成一次（最多一轮 repair）。"""
        started = datetime.now(UTC)
        raw = await self.model.generate_case_drafts(
            text,
            max_cases=max_cases,
            language=language,
            domain_hint=domain_hint,
            repair_issues=None,
        )
        drafts, issues = self._validate_raw(raw.raw_drafts)
        run.trace.steps.append(
            StepRecord(
                "generate_cases",
                "succeeded",
                started,
                datetime.now(UTC),
                summary=f"raw={len(raw.raw_drafts)}",
                prompt_tokens=raw.prompt_tokens,
                completion_tokens=raw.completion_tokens,
            )
        )
        if issues:
            # 把校验失败信息回传给模型，期望修掉非法草稿；仍可能留下 PARTIAL
            started = datetime.now(UTC)
            raw = await self.model.generate_case_drafts(
                text,
                max_cases=max_cases,
                language=language,
                domain_hint=domain_hint,
                repair_issues=[i.message for i in issues],
            )
            drafts, issues = self._validate_raw(raw.raw_drafts)
            run.trace.steps.append(
                StepRecord(
                    "validate_cases",
                    "succeeded",
                    started,
                    datetime.now(UTC),
                    summary=f"retry valid={len(drafts)} issues={len(issues)}",
                )
            )
        else:
            run.trace.steps.append(
                StepRecord(
                    "validate_cases",
                    "succeeded",
                    datetime.now(UTC),
                    datetime.now(UTC),
                    summary="ok",
                )
            )
        return drafts, issues

    def _validate_raw(
        self, raw_drafts: list[dict[str, object]]
    ) -> tuple[list[CaseDraft], list[Issue]]:
        """逐条解析模型 JSON：合法进 drafts，非法进 issues（不中断整批）。"""
        valid: list[CaseDraft] = []
        issues: list[Issue] = []
        for idx, item in enumerate(raw_drafts or []):
            try:
                if not isinstance(item, dict):
                    raise CaseDraftValidationError("草稿必须是对象", field=None)
                steps_raw = item.get("steps") or []
                if not isinstance(steps_raw, list):
                    raise CaseDraftValidationError("steps 必须是数组", field="steps")
                steps: list[TestStep] = []
                for step_i, s in enumerate(steps_raw):
                    if not isinstance(s, dict):
                        raise CaseDraftValidationError(
                            "步骤必须是对象",
                            field=f"steps[{step_i}]",
                        )
                    step_dict = cast(dict[str, Any], s)
                    steps.append(
                        TestStep(
                            action=str(step_dict.get("action", "")),
                            expected=str(step_dict.get("expected", "")),
                            test_data=_optional_str(step_dict.get("test_data")),
                        )
                    )
                priority = item.get("priority")
                rationale = item.get("rationale")
                preconditions_raw = item.get("preconditions") or []
                tags_raw = item.get("tags") or []
                if not isinstance(preconditions_raw, list):
                    raise CaseDraftValidationError(
                        "preconditions 必须是数组", field="preconditions"
                    )
                if not isinstance(tags_raw, list):
                    raise CaseDraftValidationError("tags 必须是数组", field="tags")
                draft = CaseDraft(
                    title=str(item.get("title", "")),
                    preconditions=[str(x) for x in preconditions_raw],
                    steps=steps,
                    priority=str(priority) if priority is not None else None,
                    tags=[str(x) for x in tags_raw],
                    rationale=str(rationale) if rationale is not None else None,
                )
                draft.validate()
                valid.append(draft)
            except (CaseDraftValidationError, TypeError, ValueError, AttributeError) as exc:
                field = getattr(exc, "field", None)
                issues.append(
                    Issue(
                        "DRAFT_VALIDATION_FAILED",
                        str(exc),
                        draft_index=idx,
                        field=field if isinstance(field, str) else None,
                    )
                )
        # 模型返回空列表时也要给出可观测 issue，避免「静默成功但无草稿」
        if not valid and not issues:
            issues.append(Issue("NO_VALID_DRAFTS", "模型未返回任何用例草稿"))
        return valid, issues


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
