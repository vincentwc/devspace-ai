from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Response, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.infrastructure.config.logging import configure_logging
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.factory import build_model_adapter
from devspace_ai.infrastructure.persistence.pg_run_repository import PgRunRepository
from devspace_ai.interfaces.rest.errors import input_rejected_handler
from devspace_ai.interfaces.rest.routes_case_drafts import router as case_drafts_router


def create_app(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[str], Engine] | None = None,
    case_generation_service: CaseGenerationService | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="devspace-ai", version="0.1.0")
    app.state.settings = settings

    if case_generation_service is None:
        model = build_model_adapter(settings)
        runs = PgRunRepository(settings.database_url)
        case_generation_service = CaseGenerationService(settings, model, runs)
    app.state.case_generation_service = case_generation_service

    app.add_exception_handler(InputRejectedError, input_rejected_handler)
    app.include_router(case_drafts_router)

    make_engine = engine_factory or (lambda url: create_engine(url, pool_pre_ping=True))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(response: Response) -> dict[str, str]:
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
    return create_app()
