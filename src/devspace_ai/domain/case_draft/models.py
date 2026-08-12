from dataclasses import dataclass, field

from .errors import CaseDraftValidationError

ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}


@dataclass(frozen=True)
class TestStep:
    action: str
    expected: str
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
    rationale: str | None = None

    def validate(self) -> None:
        if not self.title or not self.title.strip():
            raise CaseDraftValidationError("title must be non-empty", field="title")
        if not self.steps:
            raise CaseDraftValidationError("steps must contain at least one item", field="steps")
        if self.priority is not None and self.priority not in ALLOWED_PRIORITIES:
            raise CaseDraftValidationError("invalid priority", field="priority")
        normalized_steps: list[TestStep] = []
        for i, step in enumerate(self.steps):
            ns = step.normalized()
            if not ns.action:
                raise CaseDraftValidationError(
                    "action must be non-empty",
                    field=f"steps[{i}].action",
                )
            if not ns.expected:
                raise CaseDraftValidationError(
                    "expected must be non-empty",
                    field=f"steps[{i}].expected",
                )
            normalized_steps.append(ns)
        self.title = self.title.strip()
        self.steps = normalized_steps
