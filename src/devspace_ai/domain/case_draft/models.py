"""用例草稿领域模型。

注意：这是「AI 产出的待确认草稿」，不是业务系统里已落库的正式用例。
"""

from dataclasses import dataclass, field

from .errors import CaseDraftValidationError

# 与常见测试优先级约定对齐；priority 可为 None（模型未给出时）
ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}


@dataclass(frozen=True)
class TestStep:
    # 避免被 pytest 误收集为测试类
    __test__ = False

    action: str
    expected: str
    # 可选测试数据；空字符串在 normalized() 时归一成 None
    test_data: str | None = None

    def normalized(self) -> "TestStep":
        data = self.test_data
        if data is not None and data.strip() == "":
            data = None
        return TestStep(action=self.action.strip(), expected=self.expected.strip(), test_data=data)


@dataclass
class CaseDraft:
    title: str
    preconditions: list[str] = field(default_factory=list)
    steps: list[TestStep] = field(default_factory=list)
    priority: str | None = None
    tags: list[str] = field(default_factory=list)
    # 模型给出的「为何生成此用例」说明，供人工审阅
    rationale: str | None = None

    def validate(self) -> None:
        """就地校验并规范化；失败抛 CaseDraftValidationError（含 field 路径）。"""
        if not self.title or not self.title.strip():
            raise CaseDraftValidationError("标题不能为空", field="title")
        if not self.steps:
            raise CaseDraftValidationError("步骤至少需要一条", field="steps")
        if self.priority is not None and self.priority not in ALLOWED_PRIORITIES:
            raise CaseDraftValidationError("优先级无效", field="priority")
        normalized_steps: list[TestStep] = []
        for i, step in enumerate(self.steps):
            ns = step.normalized()
            if not ns.action:
                raise CaseDraftValidationError(
                    "操作步骤不能为空",
                    field=f"steps[{i}].action",
                )
            if not ns.expected:
                raise CaseDraftValidationError(
                    "预期结果不能为空",
                    field=f"steps[{i}].expected",
                )
            normalized_steps.append(ns)
        self.title = self.title.strip()
        self.steps = normalized_steps
