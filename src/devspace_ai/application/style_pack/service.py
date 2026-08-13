"""风格包应用服务：内置合并读取、写路径校验与只读保护。"""

from __future__ import annotations

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.port.outbound.style_pack_repository_port import (
    StylePackRepositoryPort,
)
from devspace_ai.application.style_pack.errors import PackNotFoundError
from devspace_ai.domain.style_pack.errors import StylePackError
from devspace_ai.domain.style_pack.models import MAX_USER_PACKS, StylePack
from devspace_ai.infrastructure.style_pack.builtins import get_builtin, list_builtins


class StylePackService:
    def __init__(self, repo: StylePackRepositoryPort) -> None:
        self.repo = repo

    def list_all(self) -> list[StylePack]:
        return [*list_builtins(), *self.repo.list_user()]

    def get(self, pack_id: str) -> StylePack:
        builtin = get_builtin(pack_id)
        if builtin is not None:
            return builtin
        try:
            pack = self.repo.get(pack_id)
        except StylePackError as exc:
            raise InputRejectedError("INVALID_EXAMPLE", exc.message, field=exc.field) from exc
        if pack is None:
            raise PackNotFoundError()
        try:
            pack.validate()
        except StylePackError as exc:
            raise InputRejectedError("INVALID_EXAMPLE", exc.message, field=exc.field) from exc
        return pack

    def create(self, pack: StylePack) -> StylePack:
        pack.builtin = False
        try:
            pack.validate()
        except StylePackError as exc:
            raise InputRejectedError(exc.code, exc.message, field=exc.field) from exc
        if self.repo.count() >= MAX_USER_PACKS:
            raise InputRejectedError(
                "PACK_LIMIT",
                f"自建风格包最多 {MAX_USER_PACKS} 个",
            )
        try:
            return self.repo.create(pack)
        except StylePackError as exc:
            raise InputRejectedError(exc.code, exc.message, field=exc.field) from exc

    def update(self, pack: StylePack) -> StylePack:
        if get_builtin(pack.id) is not None:
            raise InputRejectedError("PACK_READONLY", "系统示例不能修改")
        existing = self.repo.get(pack.id)
        if existing is None:
            raise PackNotFoundError()
        pack.key = existing.key
        pack.builtin = False
        try:
            pack.validate()
        except StylePackError as exc:
            raise InputRejectedError(exc.code, exc.message, field=exc.field) from exc
        try:
            updated = self.repo.update(pack)
        except StylePackError as exc:
            raise InputRejectedError(exc.code, exc.message, field=exc.field) from exc
        if updated is None:
            raise PackNotFoundError()
        return updated

    def delete(self, pack_id: str) -> None:
        if get_builtin(pack_id) is not None:
            raise InputRejectedError("PACK_READONLY", "系统示例不能删除")
        if not self.repo.delete(pack_id):
            raise PackNotFoundError()
