from devspace_ai.infrastructure.prompt.case_generation import build_messages
from devspace_ai.infrastructure.style_pack.builtins import BUILTIN_PAYMENT_ID, get_builtin


def test_messages_include_style_pack_block() -> None:
    pack = get_builtin(BUILTIN_PAYMENT_ID)
    assert pack is not None
    msgs = build_messages(
        "分期订单部分退款",
        max_cases=10,
        language="zh-CN",
        domain_hint="金融",
        repair_issues=None,
        style_pack=pack,
    )
    user = str(msgs[1]["content"])
    assert "Style pack:" in user
    assert pack.key in user
    assert pack.examples[0].requirement_text in user
    assert "Domain hint:" in user
    system = str(msgs[0]["content"])
    assert "范文" in system or "style" in system.lower() or "imitate" in system.lower()


def test_messages_without_pack_have_no_style_block() -> None:
    msgs = build_messages(
        "登录",
        max_cases=3,
        language="zh-CN",
        domain_hint=None,
        repair_issues=None,
        style_pack=None,
    )
    assert "Style pack:" not in str(msgs[1]["content"])
