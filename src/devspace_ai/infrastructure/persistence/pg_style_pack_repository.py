"""StylePack（用户包）的 Postgres 仓储实现。

builtin 包不落此表；examples 以 JSONB 存储，读写用 asdict / 手工还原 CaseDraft。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.errors import StylePackError
from devspace_ai.domain.style_pack.models import StyleExample, StylePack
from devspace_ai.infrastructure.persistence.db import create_db_engine, create_session_factory
from devspace_ai.infrastructure.persistence.models import StylePackRow

_RESTORE_ERRORS = (KeyError, TypeError, ValueError, AttributeError)


def _serialize_examples(examples: list[StyleExample]) -> list[dict[str, object]]:
    return [
        {
            "label": ex.label,
            "requirement_text": ex.requirement_text,
            "drafts": [asdict(d) for d in ex.drafts],
        }
        for ex in examples
    ]


def _deserialize_draft(raw: dict[str, Any]) -> CaseDraft:
    return CaseDraft(
        title=raw["title"],
        preconditions=raw.get("preconditions") or [],
        steps=[TestStep(**s) for s in raw.get("steps") or []],
        priority=raw.get("priority"),
        tags=raw.get("tags") or [],
        rationale=raw.get("rationale"),
    )


def _deserialize_examples(raw: list[dict[str, Any]] | None) -> list[StyleExample]:
    return [
        StyleExample(
            label=item.get("label"),
            requirement_text=item["requirement_text"],
            drafts=[_deserialize_draft(d) for d in item.get("drafts") or []],
        )
        for item in raw or []
    ]


def _stub_from_row(row: StylePackRow) -> StylePack:
    return StylePack(
        id=row.id,
        key=row.key,
        name=row.name,
        description=row.description,
        examples=[],
        builtin=False,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_pack(row: StylePackRow) -> StylePack:
    try:
        raw = row.examples
        if not isinstance(raw, list):
            raise TypeError("examples must be a list")
        return StylePack(
            id=row.id,
            key=row.key,
            name=row.name,
            description=row.description,
            examples=_deserialize_examples(raw),
            builtin=False,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except _RESTORE_ERRORS as exc:
        raise StylePackError(
            "INVALID_EXAMPLE",
            "风格包范文无法还原",
            field="examples",
        ) from exc


class PgStylePackRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_db_engine(database_url)
        self._session_factory = create_session_factory(self._engine)

    def list_user(self) -> list[StylePack]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(StylePackRow).order_by(StylePackRow.updated_at.desc())
            ).all()
            packs: list[StylePack] = []
            for row in rows:
                try:
                    packs.append(_row_to_pack(row))
                except StylePackError:
                    packs.append(_stub_from_row(row))
            return packs

    def get(self, id: str) -> StylePack | None:
        with self._session_factory() as session:
            row = session.get(StylePackRow, id)
            if row is None:
                return None
            return _row_to_pack(row)

    def get_by_key(self, key: str) -> StylePack | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(StylePackRow).where(StylePackRow.key == key).limit(1)
            ).first()
            if row is None:
                return None
            try:
                return _row_to_pack(row)
            except StylePackError:
                return _stub_from_row(row)

    def create(self, pack: StylePack) -> StylePack:
        if self.get_by_key(pack.key) is not None:
            raise StylePackError("DUPLICATE_KEY", "代号已存在", field="key")
        now = datetime.now(UTC)
        with self._session_factory() as session:
            row = StylePackRow(
                id=pack.id,
                key=pack.key,
                name=pack.name,
                description=pack.description,
                examples=_serialize_examples(pack.examples),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise StylePackError("DUPLICATE_KEY", "代号已存在", field="key") from None
            session.refresh(row)
            return _row_to_pack(row)

    def update(self, pack: StylePack) -> StylePack | None:
        with self._session_factory() as session:
            row = session.get(StylePackRow, pack.id)
            if row is None:
                return None
            row.name = pack.name
            row.description = pack.description
            row.examples = _serialize_examples(pack.examples)
            row.updated_at = datetime.now(UTC)
            # 不改 key
            session.commit()
            session.refresh(row)
            return _row_to_pack(row)

    def delete(self, id: str) -> bool:
        with self._session_factory() as session:
            row = session.get(StylePackRow, id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def count(self) -> int:
        with self._session_factory() as session:
            return int(session.scalar(select(func.count()).select_from(StylePackRow)) or 0)
