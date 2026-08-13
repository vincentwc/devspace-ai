"""将应用层输入拒绝异常统一成 `{issues:[{code,message,field}]}` 形态。"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.style_pack.errors import IssuesRejectedError, PackNotFoundError


async def input_rejected_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, InputRejectedError):
        raise exc
    return JSONResponse(
        status_code=400,
        content={
            "issues": [
                {
                    "code": exc.code,
                    "message": exc.message,
                    "field": exc.field,
                }
            ]
        },
    )


async def pack_not_found_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, PackNotFoundError):
        raise exc
    return JSONResponse(
        status_code=404,
        content={
            "issues": [
                {
                    "code": exc.code,
                    "message": exc.message,
                    "field": None,
                }
            ]
        },
    )


async def issues_rejected_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, IssuesRejectedError):
        raise exc
    return JSONResponse(
        status_code=400,
        content={
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "field": issue.field,
                }
                for issue in exc.issues
            ]
        },
    )
