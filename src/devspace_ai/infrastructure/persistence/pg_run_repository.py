"""GenerationRun 的 Postgres 仓储实现。

表结构刻意「瘦」：常用列（run_id/status/created_at/input_text）+ payload JSONB。
草稿、issues、trace 放进 payload，避免早期过度拆表。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.run.models import (
    GenerationRun,
    Issue,
    RunStatus,
    RunTrace,
    StepRecord,
)
from devspace_ai.infrastructure.persistence.db import create_db_engine, create_session_factory
from devspace_ai.infrastructure.persistence.models import GenerationRunRow


def _serialize_payload(run: GenerationRun) -> dict[str, object]:
    """领域对象 → JSONB；datetime 转 ISO 字符串。"""
    steps: list[dict[str, object]] = []
    for s in run.trace.steps:
        item = asdict(s)
        item["started_at"] = s.started_at.isoformat()
        item["ended_at"] = s.ended_at.isoformat() if s.ended_at else None
        steps.append(item)
    return {
        "drafts": [asdict(d) for d in run.drafts],
        "trace": {"steps": steps},
        "issues": [asdict(i) for i in run.issues],
        "error": run.error,
    }


def _deserialize_run(row: GenerationRunRow) -> GenerationRun:
    """行记录 → 领域 GenerationRun。"""
    payload: dict[str, Any] = dict(row.payload or {})
    drafts = [
        CaseDraft(
            title=d["title"],
            preconditions=d.get("preconditions") or [],
            steps=[TestStep(**s) for s in d.get("steps") or []],
            priority=d.get("priority"),
            tags=d.get("tags") or [],
            rationale=d.get("rationale"),
        )
        for d in payload.get("drafts") or []
    ]
    issues = [Issue(**i) for i in payload.get("issues") or []]
    steps: list[StepRecord] = []
    for s in (payload.get("trace") or {}).get("steps") or []:
        steps.append(
            StepRecord(
                step_name=s["step_name"],
                status=s["status"],
                started_at=datetime.fromisoformat(s["started_at"]),
                ended_at=datetime.fromisoformat(s["ended_at"]) if s.get("ended_at") else None,
                summary=s.get("summary"),
                error=s.get("error"),
                prompt_tokens=s.get("prompt_tokens"),
                completion_tokens=s.get("completion_tokens"),
            )
        )
    return GenerationRun(
        run_id=row.run_id,
        status=RunStatus(row.status),
        input_text=row.input_text,
        drafts=drafts,
        issues=issues,
        trace=RunTrace(steps=steps),
        error=payload.get("error"),
    )


class PgRunRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_db_engine(database_url)
        self._session_factory = create_session_factory(self._engine)

    def save(self, run: GenerationRun) -> None:
        # merge：同 run_id 重复保存时更新 payload/status，保留首次 created_at
        payload = _serialize_payload(run)
        with self._session_factory() as session:
            existing = session.get(GenerationRunRow, run.run_id)
            created_at = existing.created_at if existing is not None else datetime.now(UTC)
            row = GenerationRunRow(
                run_id=run.run_id,
                status=run.status.value,
                created_at=created_at,
                input_text=run.input_text,
                payload=payload,
            )
            session.merge(row)
            session.commit()

    def get(self, run_id: str) -> GenerationRun | None:
        with self._session_factory() as session:
            row = session.get(GenerationRunRow, run_id)
            if row is None:
                return None
            return _deserialize_run(row)

    def list_recent(self, limit: int = 20) -> list[GenerationRun]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(GenerationRunRow).order_by(GenerationRunRow.created_at.desc()).limit(limit)
            ).all()
            return [_deserialize_run(row) for row in rows]
