"""用例草稿生成提示词。

`repair_issues` 非空时追加修正指令，驱动模型整包重出 JSON（不是局部 patch）。
`style_pack` 非空时注入范文块，供模型模仿结构与粒度（Task 7 会真正传入包）。
"""

from __future__ import annotations

import json
from dataclasses import asdict

from devspace_ai.domain.style_pack.models import StylePack

# 嵌入 system prompt，约束返回字段，减少自由文本
SCHEMA_HINT = {
    "drafts": [
        {
            "title": "string",
            "preconditions": ["string"],
            "steps": [{"action": "string", "expected": "string", "test_data": "string|null"}],
            "priority": "P0|P1|P2|P3|null",
            "tags": ["string"],
            "rationale": "string|null",
        }
    ]
}


def format_style_pack_block(pack: StylePack) -> str:
    """格式化风格包范文块，供 build_messages 与 Task 7 字符计数复用。"""
    lines = [f"Style pack: {pack.name} ({pack.key})"]
    for i, ex in enumerate(pack.examples, start=1):
        lines.append(f"Example {i}")
        lines.append(ex.requirement_text)
        lines.append(json.dumps([asdict(d) for d in ex.drafts], ensure_ascii=False))
    return "\n".join(lines)


def build_messages(
    requirement_text: str,
    *,
    max_cases: int,
    language: str,
    domain_hint: str | None,
    repair_issues: list[str] | None,
    style_pack: StylePack | None = None,
) -> list[dict[str, object]]:
    system = (
        "You generate manual test case drafts as JSON only. "
        f"Language={language}. Return at most {max_cases} drafts. "
        "Each step needs action, expected, test_data (null if no concrete data). "
        f"Schema: {json.dumps(SCHEMA_HINT, ensure_ascii=False)}"
    )
    if style_pack is not None:
        system += (
            " When a style pack is provided, imitate its structure, step granularity, "
            "and wording; do not copy the example requirements as the new cases."
        )
    parts = [requirement_text]
    if style_pack is not None:
        parts.append(format_style_pack_block(style_pack))
    if domain_hint:
        parts.append(f"Domain hint:\n{domain_hint}")
    user = "\n\n".join(parts)
    if repair_issues:
        user += "\n\n请根据以下校验问题修正，并重新返回完整 JSON：\n- " + "\n- ".join(repair_issues)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
