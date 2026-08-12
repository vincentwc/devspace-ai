from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.interfaces.rest.schemas import GenerationRunDTO, result_to_dto, run_to_dto

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/debug", tags=["debug-ui"])


def _service(request: Request) -> CaseGenerationService:
    return cast(CaseGenerationService, request.app.state.case_generation_service)


def _run_context(dto: GenerationRunDTO) -> dict[str, Any]:
    payload = dto.model_dump(mode="json")
    return {
        "run": dto,
        "json_block": json.dumps(payload, ensure_ascii=False, indent=2),
    }


@router.get("/", response_class=HTMLResponse)
async def debug_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "调试生成", "error": None},
    )


@router.post("/generate", response_class=HTMLResponse)
async def debug_generate(
    request: Request,
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    language: Annotated[str, Form()] = "zh-CN",
    max_cases: Annotated[int | None, Form()] = None,
    domain_hint: Annotated[str | None, Form()] = None,
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
    )
    try:
        result = await _service(request).generate(command)
    except InputRejectedError as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": "调试生成",
                "error": f"{exc.code}: {exc.message}",
                "language": language,
                "max_cases": max_cases,
                "domain_hint": domain_hint,
                "text": text or "",
            },
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
            {"title": "调试生成", "error": f"run not found: {run_id}"},
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
