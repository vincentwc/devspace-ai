from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Response, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from devspace_ai.infrastructure.config.logging import configure_logging
from devspace_ai.infrastructure.config.settings import Settings


def create_app(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[str], Engine] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="devspace-ai", version="0.1.0")
    app.state.settings = settings

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
