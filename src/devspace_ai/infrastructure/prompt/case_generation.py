import json

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
) -> list[dict]:
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
        user += "\n\nFix these validation issues and return full JSON again:\n- " + "\n- ".join(
            repair_issues
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
