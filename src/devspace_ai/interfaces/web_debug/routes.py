"""Jinja 调试页：本地快速试生成，不替代正式 REST 集成。

路由挂在 /debug，是否启用由 Settings.debug_ui_enabled() 决定。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.style_pack.errors import PackNotFoundError
from devspace_ai.application.style_pack.service import StylePackService
from devspace_ai.interfaces.rest.schemas import GenerationRunDTO, result_to_dto, run_to_dto

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/debug", tags=["debug-ui"])


def _service(request: Request) -> CaseGenerationService:
    return cast(CaseGenerationService, request.app.state.case_generation_service)


def _style_pack_service(request: Request) -> StylePackService:
    return cast(StylePackService, request.app.state.style_pack_service)


def _run_context(dto: GenerationRunDTO) -> dict[str, Any]:
    """模板既渲染结构化字段，也给一份完整 JSON 便于复制。"""
    payload = dto.model_dump(mode="json")
    return {
        "run": dto,
        "json_block": json.dumps(payload, ensure_ascii=False, indent=2),
    }


def _generate_page_vars(request: Request, **extra: Any) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "title": "调试生成",
        "error": None,
        "style_packs": _style_pack_service(request).list_all(),
    }
    ctx.update(extra)
    return ctx


def _form_context(
    *,
    title: str,
    mode: str,
    pack_id: str,
    name: str,
    key: str,
    key_readonly: bool,
    description: str,
    examples: list[Any],
) -> dict[str, Any]:
    return {
        "title": title,
        "mode": mode,
        "pack_id": pack_id,
        "name": name,
        "key": key,
        "key_readonly": key_readonly,
        "description": description,
        "examples": examples,
    }


@router.get("/static/style_pack_form.js")
def style_pack_form_js() -> FileResponse:
    return FileResponse(STATIC_DIR / "style_pack_form.js", media_type="text/javascript")


@router.get("/", response_class=HTMLResponse)
async def debug_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        _generate_page_vars(request),
    )


@router.post("/generate", response_class=HTMLResponse)
async def debug_generate(
    request: Request,
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    language: Annotated[str, Form()] = "zh-CN",
    max_cases: Annotated[int | None, Form()] = None,
    domain_hint: Annotated[str | None, Form()] = None,
    style_pack_id: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    file_name: str | None = None
    file_bytes: bytes | None = None
    if file is not None and file.filename:
        file_name = file.filename
        file_bytes = await file.read()

    command = GenerateCaseDraftsCommand(
        text=text,
        file_name=file_name,
        file_bytes=file_bytes,
        language=language,
        max_cases=max_cases,
        domain_hint=domain_hint,
        style_pack_id=style_pack_id,
    )
    try:
        result = await _service(request).generate(command)
    except InputRejectedError as exc:
        # 输入类错误回表单页展示，不跳详情
        return templates.TemplateResponse(
            request,
            "index.html",
            _generate_page_vars(
                request,
                error=f"{exc.code}: {exc.message}",
                language=language,
                max_cases=max_cases,
                domain_hint=domain_hint,
                style_pack_id=style_pack_id or "",
                text=text or "",
            ),
            status_code=400,
        )

    dto = result_to_dto(result)
    ctx = _run_context(dto)
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "title": f"Run {dto.run_id}",
            **ctx,
        },
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def debug_run_detail(request: Request, run_id: str) -> HTMLResponse:
    run = _service(request).runs.get(run_id)
    if run is None:
        return templates.TemplateResponse(
            request,
            "index.html",
            _generate_page_vars(request, error=f"未找到运行记录：{run_id}"),
            status_code=404,
        )
    dto = run_to_dto(run)
    ctx = _run_context(dto)
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "title": f"Run {dto.run_id}",
            **ctx,
        },
    )


@router.get("/style-packs", response_class=HTMLResponse)
async def style_packs_list(request: Request) -> HTMLResponse:
    packs = _style_pack_service(request).list_all()
    return templates.TemplateResponse(
        request,
        "style_packs_list.html",
        {
            "title": "风格包",
            "builtins": [p for p in packs if p.builtin],
            "user_packs": [p for p in packs if not p.builtin],
        },
    )


@router.get("/style-packs/new", response_class=HTMLResponse)
async def style_pack_new(
    request: Request,
    from_id: Annotated[str | None, Query(alias="from")] = None,
) -> HTMLResponse:
    name = ""
    key = ""
    description = ""
    examples: list[Any] = []
    if from_id:
        try:
            src = _style_pack_service(request).get(from_id)
        except PackNotFoundError:
            src = None
        if src is not None:
            name = f"{src.name}（副本）"
            description = src.description or ""
            examples = src.examples
    return templates.TemplateResponse(
        request,
        "style_pack_form.html",
        _form_context(
            title="新建风格包",
            mode="create",
            pack_id="",
            name=name,
            key=key,
            key_readonly=False,
            description=description,
            examples=examples,
        ),
    )


@router.get("/style-packs/{pack_id}/edit", response_class=HTMLResponse)
async def style_pack_edit(request: Request, pack_id: str) -> Response:
    try:
        pack = _style_pack_service(request).get(pack_id)
    except PackNotFoundError:
        return templates.TemplateResponse(
            request,
            "style_pack_view.html",
            {"title": "风格包不存在", "pack": None, "error": "风格包不存在"},
            status_code=404,
        )
    if pack.builtin:
        return RedirectResponse(
            url=f"/debug/style-packs/new?from={pack_id}",
            status_code=302,
        )
    return templates.TemplateResponse(
        request,
        "style_pack_form.html",
        _form_context(
            title="编辑风格包",
            mode="edit",
            pack_id=pack.id,
            name=pack.name,
            key=pack.key,
            key_readonly=True,
            description=pack.description or "",
            examples=pack.examples,
        ),
    )


@router.get("/style-packs/{pack_id}", response_class=HTMLResponse)
async def style_pack_view(request: Request, pack_id: str) -> HTMLResponse:
    try:
        pack = _style_pack_service(request).get(pack_id)
    except PackNotFoundError:
        return templates.TemplateResponse(
            request,
            "style_pack_view.html",
            {"title": "风格包不存在", "pack": None, "error": "风格包不存在"},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "style_pack_view.html",
        {"title": pack.name, "pack": pack, "error": None},
    )
