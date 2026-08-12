from dataclasses import dataclass


@dataclass
class GenerateCaseDraftsCommand:
    text: str | None
    file_name: str | None
    file_bytes: bytes | None
    language: str = "zh-CN"
    max_cases: int | None = None
    domain_hint: str | None = None
