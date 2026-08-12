"""出站端口：用例草稿生成模型。

应用层只依赖本协议；Fake / OpenAI Compatible 在 infrastructure 实现。
`repair_issues` 非空时表示带着上一轮校验问题做修正生成。
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelGenerationResult:
    # 尚未经领域校验的原始 dict 列表
    raw_drafts: list[dict[str, object]]
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ModelPort(Protocol):
    async def generate_case_drafts(
        self,
        requirement_text: str,
        *,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        repair_issues: list[str] | None,
    ) -> ModelGenerationResult: ...
