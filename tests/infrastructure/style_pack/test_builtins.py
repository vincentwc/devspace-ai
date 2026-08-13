from devspace_ai.infrastructure.style_pack.builtins import (
    BUILTIN_MARKETING_ID,
    BUILTIN_PAYMENT_ID,
    get_builtin,
    list_builtins,
)


def test_two_builtins_validate_and_cover_structure() -> None:
    packs = list_builtins()
    assert len(packs) == 2
    assert {p.id for p in packs} == {BUILTIN_PAYMENT_ID, BUILTIN_MARKETING_ID}
    for pack in packs:
        pack.validate()
        assert pack.builtin is True
        assert pack.key.startswith("example.")
        assert len(pack.examples) >= 2
        assert any(len(ex.drafts) >= 2 for ex in pack.examples)
        datas = [step.test_data for ex in pack.examples for d in ex.drafts for step in d.steps]
        assert any(x is None for x in datas)
        assert any(x is not None for x in datas)


def test_get_builtin_unknown() -> None:
    assert get_builtin("not-a-builtin") is None
