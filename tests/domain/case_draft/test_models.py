import pytest
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.case_draft.errors import CaseDraftValidationError


def test_valid_draft_allows_null_test_data():
    draft = CaseDraft(
        title="登录成功",
        preconditions=["已注册用户"],
        steps=[TestStep(action="输入账号密码", expected="进入首页", test_data=None)],
        priority="P1",
        tags=["auth"],
        rationale="覆盖主路径",
    )
    draft.validate()


def test_empty_test_data_normalized_to_none():
    step = TestStep(action="a", expected="b", test_data="")
    assert step.normalized().test_data is None


def test_rejects_empty_title_or_steps():
    with pytest.raises(CaseDraftValidationError):
        CaseDraft(
            title=" ",
            preconditions=[],
            steps=[TestStep("a", "b", None)],
            priority=None,
            tags=[],
            rationale=None,
        ).validate()
    with pytest.raises(CaseDraftValidationError):
        CaseDraft(title="t", preconditions=[], steps=[], priority=None, tags=[], rationale=None).validate()
