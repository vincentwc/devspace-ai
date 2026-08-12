"""确定性假模型：本地开发与 CI 不依赖真实 LLM。

输出形状与正式适配器一致，便于打通 Graph / 校验 / 持久化整条链路。
"""

from devspace_ai.application.port.outbound.model_port import ModelGenerationResult


class FakeModelAdapter:
    async def generate_case_drafts(
        self,
        requirement_text: str,
        *,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        repair_issues: list[str] | None,
    ) -> ModelGenerationResult:
        drafts: list[dict[str, object]] = [
            {
                "title": "主路径验证",
                "preconditions": ["系统可用"],
                "steps": [
                    {"action": "打开功能入口", "expected": "页面加载成功", "test_data": None},
                    {"action": "提交合法数据", "expected": "操作成功", "test_data": "user=demo"},
                ],
                "priority": "P1",
                "tags": ["fake"],
                "rationale": f"based on:{requirement_text[:32]}",
            },
            {
                "title": "异常路径验证",
                "preconditions": [],
                "steps": [{"action": "提交空数据", "expected": "提示校验错误", "test_data": None}],
                "priority": "P2",
                "tags": ["fake", "negative"],
                "rationale": "cover invalid input",
            },
        ]
        return ModelGenerationResult(
            raw_drafts=drafts[:max_cases],
            model="fake",
            prompt_tokens=0,
            completion_tokens=0,
        )
