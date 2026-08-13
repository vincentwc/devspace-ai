from datetime import UTC, datetime

from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.models import StyleExample, StylePack

BUILTIN_PAYMENT_ID = "00000000-0000-4000-8000-000000000001"
BUILTIN_MARKETING_ID = "00000000-0000-4000-8000-000000000002"
_TS = datetime(2026, 8, 13, tzinfo=UTC)


def _step(action: str, expected: str, test_data: str | None = None) -> TestStep:
    return TestStep(action=action, expected=expected, test_data=test_data)


def _payment() -> StylePack:
    return StylePack(
        id=BUILTIN_PAYMENT_ID,
        key="example.payment.api",
        name="示例 · 支付接口",
        description="支付/退款接口测试写法教材",
        builtin=True,
        created_at=_TS,
        updated_at=_TS,
        examples=[
            StyleExample(
                label="退款成功",
                requirement_text="用户已支付成功，在订单详情点击退款，退款金额等于实付金额，应退回原支付渠道。",
                drafts=[
                    CaseDraft(
                        title="订单详情原路退款成功",
                        preconditions=["订单已支付", "退款渠道可用"],
                        steps=[
                            _step("打开订单详情", "页面展示实付金额", None),
                            _step("点击退款并确认金额", "提示退款受理", "100.00"),
                        ],
                        priority="P0",
                        tags=["pay", "refund"],
                    )
                ],
            ),
            StyleExample(
                label="超额退款",
                requirement_text="用户尝试将退款金额填写为大于实付金额。",
                drafts=[
                    CaseDraft(
                        title="退款金额超过实付被拒绝",
                        preconditions=["订单已支付"],
                        steps=[_step("提交超额退款", "提示金额非法", "99999")],
                        priority="P1",
                        tags=["pay", "negative"],
                    ),
                    CaseDraft(
                        title="重复提交退款",
                        preconditions=["退款已受理"],
                        steps=[_step("再次点击退款", "提示请勿重复提交", None)],
                        priority="P2",
                        tags=["pay"],
                    ),
                ],
            ),
        ],
    )


def _marketing() -> StylePack:
    return StylePack(
        id=BUILTIN_MARKETING_ID,
        key="example.marketing.web",
        name="示例 · 营销活动页",
        description="活动页领取与核销的界面测试写法教材",
        builtin=True,
        created_at=_TS,
        updated_at=_TS,
        examples=[
            StyleExample(
                label="领券",
                requirement_text="登录用户在活动页点击领取优惠券，库存充足时应领取成功。",
                drafts=[
                    CaseDraft(
                        title="活动页领取优惠券成功",
                        preconditions=["已登录", "券有库存"],
                        steps=[
                            _step("打开活动页", "展示领取按钮", None),
                            _step("点击领取", "提示领取成功并展示券码", "COUPON1"),
                        ],
                        priority="P1",
                        tags=["promo"],
                    )
                ],
            ),
            StyleExample(
                label="核销",
                requirement_text="用户在结算页使用已领取的优惠券抵扣。",
                drafts=[
                    CaseDraft(
                        title="结算页核销优惠券",
                        preconditions=["购物车有商品", "券未过期"],
                        steps=[_step("选择优惠券并提交订单", "应付金额已抵扣", None)],
                        priority="P1",
                        tags=["promo", "checkout"],
                    ),
                    CaseDraft(
                        title="过期券不可用",
                        preconditions=["券已过期"],
                        steps=[_step("尝试勾选过期券", "券置灰并提示过期", None)],
                        priority="P2",
                        tags=["promo", "negative"],
                    ),
                ],
            ),
        ],
    )


def list_builtins() -> list[StylePack]:
    packs = [_payment(), _marketing()]
    for pack in packs:
        pack.validate()
    return packs


def get_builtin(pack_id: str) -> StylePack | None:
    for pack in list_builtins():
        if pack.id == pack_id:
            return pack
    return None
