"""用例草稿生成提示词。

`repair_issues` 非空时追加修正指令，驱动模型整包重出 JSON（不是局部 patch）。
"""

import json

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


def build_messages(
    requirement_text: str,
    *,
    max_cases: int,
    language: str,
    domain_hint: str | None,
    repair_issues: list[str] | None,
) -> list[dict[str, object]]:
    system = (
        "You generate manual test case drafts as JSON only. "
        f"Language={language}. Return at most {max_cases} drafts. "
        "Each step needs action, expected, test_data (null if no concrete data). "
        f"Schema: {json.dumps(SCHEMA_HINT, ensure_ascii=False)}"
    )
    if domain_hint:
        user = f"{requirement_text}\n\nDomain hint:\n{domain_hint}"
    else:
        user = requirement_text
    if repair_issues:
        user += "\n\n请根据以下校验问题修正，并重新返回完整 JSON：\n- " + "\n- ".join(repair_issues)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
