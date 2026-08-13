from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from devspace_ai.domain.case_draft.errors import CaseDraftValidationError
from devspace_ai.domain.case_draft.models import CaseDraft
from devspace_ai.domain.style_pack.errors import StylePackError

KEY_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?$")
RESERVED_KEY_PREFIX = "example."
MAX_EXAMPLES = 5
MAX_DRAFTS_PER_EXAMPLE = 3
MAX_DRAFTS_PER_PACK = 15
MAX_NAME_LEN = 80
MAX_DESCRIPTION_LEN = 500
MAX_LABEL_LEN = 80
MAX_USER_PACKS = 50


@dataclass
class StyleExample:
    requirement_text: str
    drafts: list[CaseDraft]
    label: str | None = None


@dataclass
class StylePack:
    id: str
    key: str
    name: str
    examples: list[StyleExample]
    description: str | None = None
    builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def draft_count(self) -> int:
        return sum(len(ex.drafts) for ex in self.examples)

    def validate(self) -> None:
        name = (self.name or "").strip()
        if not name or len(name) > MAX_NAME_LEN:
            raise StylePackError("INVALID_NAME", "名称不能为空且最多 80 字", field="name")
        self.name = name
        key = (self.key or "").strip()
        if not KEY_PATTERN.fullmatch(key):
            raise StylePackError(
                "INVALID_KEY",
                "代号仅允许小写字母、数字、点、连字符，长度 1～64",
                field="key",
            )
        if not self.builtin and key.startswith(RESERVED_KEY_PREFIX):
            raise StylePackError(
                "INVALID_KEY",
                "example. 前缀为系统示例保留",
                field="key",
            )
        self.key = key
        if self.description is not None:
            desc = self.description.strip()
            if len(desc) > MAX_DESCRIPTION_LEN:
                raise StylePackError("INVALID_INPUT", "说明最多 500 字", field="description")
            self.description = desc or None
        if not self.examples:
            raise StylePackError("EMPTY_PACK", "风格包至少需要一组范文", field="examples")
        if len(self.examples) > MAX_EXAMPLES:
            raise StylePackError(
                "PACK_LIMIT",
                f"需求条数 {len(self.examples)} 超出上限 {MAX_EXAMPLES}",
                field="examples",
            )
        total = 0
        for i, ex in enumerate(self.examples):
            req = (ex.requirement_text or "").strip()
            if not req:
                raise StylePackError(
                    "INVALID_EXAMPLE",
                    "需求片段不能为空",
                    field=f"examples[{i}].requirement_text",
                )
            ex.requirement_text = req
            if ex.label is not None:
                label = ex.label.strip()
                if len(label) > MAX_LABEL_LEN:
                    raise StylePackError(
                        "INVALID_INPUT",
                        "备注最多 80 字",
                        field=f"examples[{i}].label",
                    )
                ex.label = label or None
            n = len(ex.drafts)
            if n < 1:
                raise StylePackError(
                    "INVALID_EXAMPLE",
                    f"每条需求下用例须为 1～{MAX_DRAFTS_PER_EXAMPLE} 条",
                    field=f"examples[{i}].drafts",
                )
            if n > MAX_DRAFTS_PER_EXAMPLE:
                raise StylePackError(
                    "PACK_LIMIT",
                    f"每条需求下用例最多 {MAX_DRAFTS_PER_EXAMPLE} 条",
                    field=f"examples[{i}].drafts",
                )
            for j, draft in enumerate(ex.drafts):
                try:
                    draft.validate()
                except CaseDraftValidationError as exc:
                    raise StylePackError(
                        "INVALID_EXAMPLE",
                        str(exc),
                        field=f"examples[{i}].drafts[{j}].{exc.field or 'draft'}",
                    ) from exc
            total += n
        if total > MAX_DRAFTS_PER_PACK:
            raise StylePackError(
                "PACK_LIMIT",
                f"用例合计 {total} 超出上限 {MAX_DRAFTS_PER_PACK}",
                field="examples",
            )
