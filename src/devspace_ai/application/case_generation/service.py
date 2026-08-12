from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

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
    def __init__(self, settings: Settings, model: ModelPort, runs: RunRepositoryPort) -> None:
        self.settings = settings
        self.model = model
        self.runs = runs

    async def generate(self, command: GenerateCaseDraftsCommand) -> GenerateCaseDraftsResult:
        has_text = command.text is not None and str(command.text).strip() != ""
        has_file = command.file_bytes is not None
        if has_text == has_file:
            raise InputRejectedError("INVALID_INPUT", "provide exactly one of text or file")

        if command.max_cases is None:
            max_cases = self.settings.default_max_cases
        else:
            max_cases = command.max_cases
        if max_cases > self.settings.hard_max_cases:
            raise InputRejectedError(
                "MAX_CASES_EXCEEDED",
                f"max_cases {max_cases} exceeds hard limit {self.settings.hard_max_cases}",
            )
        if max_cases < 1:
            raise InputRejectedError("INVALID_INPUT", "max_cases must be >= 1")

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
            drafts, issues = await asyncio.wait_for(
                self._generate_and_validate(
                    doc.text, max_cases, command.language, command.domain_hint, run
                ),
                timeout=self.settings.total_timeout_seconds,
            )
            status = resolve_status(len(drafts), len(issues))
            run.finish(status, drafts, issues)
        except TimeoutError:
            run.finish(
                RunStatus.FAILED,
                [],
                [Issue("MODEL_TIMEOUT", "model or total request timed out")],
            )
            run.trace.steps.append(
                StepRecord(
                    "generate_cases",
                    "failed",
                    datetime.now(UTC),
                    datetime.now(UTC),
                    error="timeout",
                )
            )
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
        valid: list[CaseDraft] = []
        issues: list[Issue] = []
        for idx, item in enumerate(raw_drafts or []):
            try:
                steps_raw = item.get("steps") or []
                if not isinstance(steps_raw, list):
                    raise CaseDraftValidationError("steps must be a list", field="steps")
                steps = [
                    TestStep(
                        action=str(cast(dict[str, Any], s).get("action", "")),
                        expected=str(cast(dict[str, Any], s).get("expected", "")),
                        test_data=_optional_str(cast(dict[str, Any], s).get("test_data")),
                    )
                    for s in steps_raw
                ]
                priority = item.get("priority")
                rationale = item.get("rationale")
                preconditions_raw = cast(list[object], item.get("preconditions") or [])
                tags_raw = cast(list[object], item.get("tags") or [])
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
            except (CaseDraftValidationError, TypeError, ValueError) as exc:
                field = getattr(exc, "field", None)
                issues.append(
                    Issue(
                        "DRAFT_VALIDATION_FAILED",
                        str(exc),
                        draft_index=idx,
                        field=field if isinstance(field, str) else None,
                    )
                )
        if not valid and not issues:
            issues.append(Issue("NO_VALID_DRAFTS", "model returned no drafts"))
        return valid, issues


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
