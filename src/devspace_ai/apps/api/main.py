"""FastAPI 组装入口：接线 Settings / Model / Repository / REST / Debug UI。

分层约定：
- interfaces：HTTP 适配
- application：用例编排
- domain：纯领域模型
- infrastructure：模型、Postgres、配置等适配器
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Response, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.style_pack.errors import IssuesRejectedError, PackNotFoundError
from devspace_ai.application.style_pack.service import StylePackService
from devspace_ai.infrastructure.config.logging import configure_logging
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.factory import build_model_adapter
from devspace_ai.infrastructure.persistence.pg_run_repository import PgRunRepository
from devspace_ai.infrastructure.persistence.pg_style_pack_repository import PgStylePackRepository
from devspace_ai.interfaces.rest.errors import (
    input_rejected_handler,
    issues_rejected_handler,
    pack_not_found_handler,
)
from devspace_ai.interfaces.rest.routes_case_drafts import router as case_drafts_router
from devspace_ai.interfaces.rest.routes_style_packs import (
    read_router as style_packs_read_router,
)
from devspace_ai.interfaces.rest.routes_style_packs import (
    write_disabled_router as style_packs_write_disabled_router,
)
from devspace_ai.interfaces.rest.routes_style_packs import (
    write_router as style_packs_write_router,
)
from devspace_ai.interfaces.web_debug.routes import router as debug_router


def create_app(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[str], Engine] | None = None,
    case_generation_service: CaseGenerationService | None = None,
    style_pack_service: StylePackService | None = None,
) -> FastAPI:
    """创建应用。测试可注入 `case_generation_service` / `engine_factory` 以避免真实外依赖。"""
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="devspace-ai", version="0.1.0")
    app.state.settings = settings

    if style_pack_service is None:
        style_pack_service = StylePackService(PgStylePackRepository(settings.database_url))
    app.state.style_pack_service = style_pack_service

    if case_generation_service is None:
        model = build_model_adapter(settings)
        runs = PgRunRepository(settings.database_url)
        case_generation_service = CaseGenerationService(settings, model, runs, style_pack_service)
    app.state.case_generation_service = case_generation_service

    app.add_exception_handler(InputRejectedError, input_rejected_handler)
    app.add_exception_handler(PackNotFoundError, pack_not_found_handler)
    app.add_exception_handler(IssuesRejectedError, issues_rejected_handler)
    app.include_router(case_drafts_router)
    app.include_router(style_packs_read_router)
    # Debug UI：local/test 默认开；生产需显式 ENABLE_DEBUG_UI=true
    if settings.debug_ui_enabled():
        app.include_router(style_packs_write_router)
        app.include_router(debug_router)
    else:
        # 同路径已有 GET 时，未注册写方法会变成 405；stub 保证写关闭仍为 404
        app.include_router(style_packs_write_disabled_router)

    make_engine = engine_factory or (lambda url: create_engine(url, pool_pre_ping=True))

    @app.get("/health")
    def health() -> dict[str, str]:
        """存活探针：进程起来即 ok，不查库。"""
        return {"status": "ok"}

    @app.get("/ready")
    def ready(response: Response) -> dict[str, str]:
        """就绪探针：能连上 Postgres 才 ready。"""
        engine: Engine | None = None
        try:
            engine = make_engine(settings.database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready"}
        finally:
            if engine is not None:
                engine.dispose()

    return app


def create_uvicorn_app() -> FastAPI:
    """Uvicorn / Docker 入口用的无参工厂。"""
    return create_app()
