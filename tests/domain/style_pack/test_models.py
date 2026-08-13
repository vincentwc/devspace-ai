import pytest

from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.errors import StylePackError
from devspace_ai.domain.style_pack.models import StyleExample, StylePack


def _draft() -> CaseDraft:
    return CaseDraft(
        title="原路退款成功",
        preconditions=["订单已支付"],
        steps=[TestStep(action="点击退款", expected="退款成功", test_data="100.00")],
        priority="P1",
        tags=["pay"],
    )


def _pack(**kwargs: object) -> StylePack:
    defaults: dict[str, object] = {
        "id": "11111111-1111-4111-8111-111111111111",
        "key": "cdp.payment.api",
        "name": "支付接口",
        "description": None,
        "examples": [
            StyleExample(label="退款", requirement_text="用户申请退款", drafts=[_draft()])
        ],
        "builtin": False,
    }
    defaults.update(kwargs)
    return StylePack(**defaults)  # type: ignore[arg-type]


def test_valid_pack_normalizes() -> None:
    pack = _pack(name="  支付接口  ")
    pack.validate()
    assert pack.name == "支付接口"


def test_empty_examples_rejected() -> None:
    pack = _pack(examples=[])
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "EMPTY_PACK"


def test_reserved_key_rejected_for_user_pack() -> None:
    pack = _pack(key="example.payment.api")
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "INVALID_KEY"


def test_reserved_key_allowed_for_builtin() -> None:
    pack = _pack(key="example.payment.api", builtin=True, name="示例 · 支付接口")
    pack.validate()


def test_too_many_examples() -> None:
    examples = [
        StyleExample(label=None, requirement_text=f"需求{i}", drafts=[_draft()]) for i in range(6)
    ]
    pack = _pack(examples=examples)
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "PACK_LIMIT"


def test_too_many_drafts_in_one_example() -> None:
    pack = _pack(
        examples=[StyleExample(label=None, requirement_text="需求", drafts=[_draft()] * 4)]
    )
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "PACK_LIMIT"


def test_empty_requirement_invalid_example() -> None:
    pack = _pack(examples=[StyleExample(label=None, requirement_text="  ", drafts=[_draft()])])
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "INVALID_EXAMPLE"
    assert ei.value.field == "examples[0].requirement_text"


def test_invalid_name() -> None:
    pack = _pack(name="   ")
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "INVALID_NAME"
