import os

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from devspace_ai.apps.api.main import create_app
from devspace_ai.infrastructure.config.settings import Settings


@pytest.fixture()
def db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai_test",
    )


@pytest.fixture()
def client(db_url: str) -> TestClient:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS generation_runs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    settings = Settings(
        _env_file=None,
        app_env="local",
        database_url=db_url,
        model_provider="fake",
        max_text_chars=1_000,
    )
    app = create_app(settings=settings)
    return TestClient(app)


def test_debug_get_form(client: TestClient) -> None:
    r = client.get("/debug/")
    assert r.status_code == 200
    assert "生成用例" in r.text


def test_debug_generate_paste(client: TestClient) -> None:
    r = client.post(
        "/debug/generate",
        data={"text": "用户可以登录系统", "language": "zh-CN"},
    )
    assert r.status_code == 200
    assert "主路径" in r.text or "draft" in r.text.lower()
    assert "ingest" in r.text or "轨迹" in r.text
    assert "test_data" in r.text or "user=demo" in r.text
    assert "JSON" in r.text or "json" in r.text.lower()


def test_debug_run_detail_replay(client: TestClient) -> None:
    created = client.post(
        "/debug/generate",
        data={"text": "用户可以登录系统", "language": "zh-CN"},
    )
    assert created.status_code == 200
    # Extract run_id from link or page content
    assert "/debug/runs/" in created.text
    start = created.text.index("/debug/runs/") + len("/debug/runs/")
    run_id = created.text[start:].split('"')[0].split("'")[0].split("<")[0].strip()
    assert run_id

    r = client.get(f"/debug/runs/{run_id}")
    assert r.status_code == 200
    assert "主路径" in r.text or "draft" in r.text.lower()
    assert "轨迹" in r.text or "ingest" in r.text


def test_debug_routes_not_mounted_when_disabled(db_url: str) -> None:
    settings = Settings(
        _env_file=None,
        app_env="prod",
        enable_debug_ui=False,
        database_url=db_url,
        model_provider="fake",
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    assert client.get("/debug/").status_code == 404
