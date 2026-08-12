"""将 InputRejectedError 统一成 `{issues:[{code,message}]}` 形态。"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from devspace_ai.application.case_generation.errors import InputRejectedError


async def input_rejected_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, InputRejectedError):
        raise exc
    return JSONResponse(
        status_code=400,
        content={"issues": [{"code": exc.code, "message": exc.message}]},
    )
