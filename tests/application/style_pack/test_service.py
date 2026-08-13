from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.style_pack.errors import PackNotFoundError
from devspace_ai.application.style_pack.service import StylePackService
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.errors import StylePackError
from devspace_ai.domain.style_pack.models import MAX_USER_PACKS, StyleExample, StylePack
from devspace_ai.infrastructure.style_pack.builtins import (
    BUILTIN_MARKETING_ID,
    BUILTIN_PAYMENT_ID,
)


class InMemoryStylePackRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, StylePack] = {}

    def list_user(self) -> list[StylePack]:
        return sorted(
            self._by_id.values(),
            key=lambda p: p.updated_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    def get(self, id: str) -> StylePack | None:
        return self._by_id.get(id)

    def create(self, pack: StylePack) -> StylePack:
        if any(p.key == pack.key for p in self._by_id.values()):
            raise StylePackError("DUPLICATE_KEY", "代号已存在", field="key")
        now = datetime.now(UTC)
        pack.created_at = pack.created_at or now
        pack.updated_at = now
        self._by_id[pack.id] = pack
        return pack

    def update(self, pack: StylePack) -> StylePack | None:
        existing = self._by_id.get(pack.id)
        if existing is None:
            return None
        pack.key = existing.key
        pack.updated_at = datetime.now(UTC)
        pack.created_at = existing.created_at
        self._by_id[pack.id] = pack
        return pack

    def delete(self, id: str) -> bool:
        return self._by_id.pop(id, None) is not None

    def count(self) -> int:
        return len(self._by_id)

    def get_by_key(self, key: str) -> StylePack | None:
        for pack in self._by_id.values():
            if pack.key == key:
                return pack
        return None


def _draft() -> CaseDraft:
    return CaseDraft(
        title="原路退款成功",
        steps=[TestStep(action="点击退款", expected="退款成功", test_data="100.00")],
    )


def _pack(**kwargs: Any) -> StylePack:
    defaults: dict[str, Any] = {
        "id": str(uuid4()),
        "key": "cdp.payment.api",
        "name": "支付接口",
        "description": None,
        "examples": [
            StyleExample(
                label="退款",
                requirement_text="用户申请退款",
                drafts=[_draft()],
            )
        ],
        "builtin": False,
    }
    defaults.update(kwargs)
    return StylePack(**defaults)


@pytest.fixture()
def service() -> StylePackService:
    return StylePackService(InMemoryStylePackRepository())


def test_list_all_builtins_first_when_empty(service: StylePackService) -> None:
    packs = service.list_all()
    assert len(packs) == 2
    assert packs[0].id == BUILTIN_PAYMENT_ID
    assert packs[1].id == BUILTIN_MARKETING_ID
    assert all(p.builtin for p in packs)


def test_create_empty_examples_raises_empty_pack(service: StylePackService) -> None:
    with pytest.raises(InputRejectedError) as ei:
        service.create(_pack(examples=[]))
    assert ei.value.code == "EMPTY_PACK"
    assert ei.value.field == "examples"


def test_create_51st_user_pack_raises_pack_limit() -> None:
    repo = MagicMock()
    repo.count.return_value = MAX_USER_PACKS
    svc = StylePackService(repo)
    with pytest.raises(InputRejectedError) as ei:
        svc.create(_pack())
    assert ei.value.code == "PACK_LIMIT"
    repo.create.assert_not_called()


def test_create_reserved_key_raises_invalid_key(service: StylePackService) -> None:
    with pytest.raises(InputRejectedError) as ei:
        service.create(_pack(key="example.x"))
    assert ei.value.code == "INVALID_KEY"
    assert ei.value.field == "key"


def test_update_builtin_raises_pack_readonly(service: StylePackService) -> None:
    with pytest.raises(InputRejectedError) as ei:
        service.update(_pack(id=BUILTIN_PAYMENT_ID, key="cdp.payment.api"))
    assert ei.value.code == "PACK_READONLY"


def test_delete_builtin_raises_pack_readonly(service: StylePackService) -> None:
    with pytest.raises(InputRejectedError) as ei:
        service.delete(BUILTIN_PAYMENT_ID)
    assert ei.value.code == "PACK_READONLY"


def test_get_builtin_ok_unknown_raises(service: StylePackService) -> None:
    pack = service.get(BUILTIN_PAYMENT_ID)
    assert pack.id == BUILTIN_PAYMENT_ID
    assert pack.builtin is True
    with pytest.raises(PackNotFoundError) as ei:
        service.get("00000000-0000-4000-8000-000000000099")
    assert ei.value.code == "PACK_NOT_FOUND"
    assert ei.value.message == "风格包不存在"


def test_create_then_list_all_length_three(service: StylePackService) -> None:
    created = service.create(_pack())
    assert created.builtin is False
    packs = service.list_all()
    assert len(packs) == 3
    assert packs[0].id == BUILTIN_PAYMENT_ID
    assert packs[1].id == BUILTIN_MARKETING_ID
    assert packs[2].id == created.id


def test_get_maps_restore_error_to_invalid_example() -> None:
    repo = MagicMock()
    repo.get.side_effect = StylePackError("INVALID_EXAMPLE", "风格包范文无法还原", field="examples")
    svc = StylePackService(repo)
    with pytest.raises(InputRejectedError) as ei:
        svc.get(str(uuid4()))
    assert ei.value.code == "INVALID_EXAMPLE"
    assert ei.value.field == "examples"


def test_get_invalid_stored_pack_raises_invalid_example() -> None:
    repo = InMemoryStylePackRepository()
    pack = _pack(examples=[])
    repo._by_id[pack.id] = pack
    svc = StylePackService(repo)
    with pytest.raises(InputRejectedError) as ei:
        svc.get(pack.id)
    assert ei.value.code == "INVALID_EXAMPLE"
