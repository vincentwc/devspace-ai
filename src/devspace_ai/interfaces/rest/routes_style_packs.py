"""风格包 REST：读路由始终挂载；写路由仅在 debug UI 开启时挂载。

写关闭时仍注册同路径 stub，避免仅 GET 已占用路径时框架返回 405 而非 404。
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status

from devspace_ai.application.style_pack.service import StylePackService
from devspace_ai.interfaces.rest.schemas import (
    StylePackCreateBody,
    StylePackDetailDTO,
    StylePackListItemDTO,
    StylePackUpdateBody,
    body_to_style_pack,
    pack_to_detail_dto,
    pack_to_list_dto,
)

read_router = APIRouter(prefix="/api/v1")
write_router = APIRouter(prefix="/api/v1")
write_disabled_router = APIRouter(prefix="/api/v1")


def _service(request: Request) -> StylePackService:
    return cast(StylePackService, request.app.state.style_pack_service)


@read_router.get("/style-packs", response_model=list[StylePackListItemDTO])
def list_style_packs(request: Request) -> list[StylePackListItemDTO]:
    return [pack_to_list_dto(p) for p in _service(request).list_all()]


@read_router.get("/style-packs/{pack_id}", response_model=StylePackDetailDTO)
def get_style_pack(request: Request, pack_id: str) -> StylePackDetailDTO:
    return pack_to_detail_dto(_service(request).get(pack_id))


@write_router.post(
    "/style-packs",
    response_model=StylePackDetailDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_style_pack(request: Request, body: StylePackCreateBody) -> StylePackDetailDTO:
    pack = body_to_style_pack(body, pack_id=str(uuid4()))
    return pack_to_detail_dto(_service(request).create(pack))


@write_router.put("/style-packs/{pack_id}", response_model=StylePackDetailDTO)
def update_style_pack(
    request: Request,
    pack_id: str,
    body: StylePackUpdateBody,
) -> StylePackDetailDTO:
    pack = body_to_style_pack(body, pack_id=pack_id)
    return pack_to_detail_dto(_service(request).update(pack))


@write_router.delete("/style-packs/{pack_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_style_pack(request: Request, pack_id: str) -> Response:
    _service(request).delete(pack_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _write_not_found() -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@write_disabled_router.post("/style-packs")
def create_style_pack_disabled() -> None:
    _write_not_found()


@write_disabled_router.put("/style-packs/{pack_id}")
def update_style_pack_disabled(pack_id: str) -> None:
    _write_not_found()


@write_disabled_router.delete("/style-packs/{pack_id}")
def delete_style_pack_disabled(pack_id: str) -> None:
    _write_not_found()
