"""用例草稿 REST：multipart 表单生成 + 按 run_id 回查。

POST 用 Form/File 是为了同时支持粘贴文本与文件上传（与调试页一致）。
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.interfaces.rest.schemas import GenerationRunDTO, result_to_dto, run_to_dto

router = APIRouter(prefix="/api/v1")


def _service(request: Request) -> CaseGenerationService:
    return cast(CaseGenerationService, request.app.state.case_generation_service)


@router.post("/case-drafts/generate", response_model=GenerationRunDTO)
async def generate_case_drafts(
    request: Request,
    text: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    language: Annotated[str, Form()] = "zh-CN",
    max_cases: Annotated[int | None, Form()] = None,
    domain_hint: Annotated[str | None, Form()] = None,
) -> GenerationRunDTO:
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
    result = await _service(request).generate(command)
    return result_to_dto(result)


@router.get("/runs/{run_id}", response_model=GenerationRunDTO)
async def get_run(request: Request, run_id: str) -> GenerationRunDTO:
    run = _service(request).runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该运行记录")
    return run_to_dto(run)
