import os

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from devspace_ai.apps.api.main import create_app
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.style_pack.builtins import BUILTIN_PAYMENT_ID


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
        conn.execute(text("DROP TABLE IF EXISTS style_packs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS generation_runs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    settings = Settings(
        _env_file=None,
        database_url=db_url,
        model_provider="fake",
        max_text_chars=1_000,
    )
    app = create_app(settings=settings)
    return TestClient(app)


def test_paste_text_returns_succeeded_with_drafts(client: TestClient) -> None:
    response = client.post(
        "/api/v1/case-drafts/generate",
        data={"text": "用户可以登录系统", "language": "zh-CN"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"succeeded", "partial"}
    assert body["run_id"]
    assert len(body["drafts"]) >= 1
    assert "trace" in body
    assert "issues" in body


def test_missing_both_fields_returns_400_invalid_input(client: TestClient) -> None:
    response = client.post("/api/v1/case-drafts/generate", data={})
    assert response.status_code == 400
    body = response.json()
    assert body["issues"][0]["code"] == "INVALID_INPUT"


def test_too_long_text_returns_400_input_too_long(client: TestClient) -> None:
    response = client.post(
        "/api/v1/case-drafts/generate",
        data={"text": "x" * 1001},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["issues"][0]["code"] == "INPUT_TOO_LONG"
    assert "1000" in body["issues"][0]["message"]


def test_get_run_by_id_after_generate(client: TestClient) -> None:
    created = client.post(
        "/api/v1/case-drafts/generate",
        data={"text": "用户可以登录系统"},
    )
    assert created.status_code == 200
    run_id = created.json()["run_id"]

    response = client.get(f"/api/v1/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["run_id"] == run_id
    assert len(response.json()["drafts"]) >= 1

    missing = client.get("/api/v1/runs/does-not-exist")
    assert missing.status_code == 404


def test_generate_with_builtin_style_pack_snapshots(client: TestClient) -> None:
    response = client.post(
        "/api/v1/case-drafts/generate",
        data={"text": "登录", "style_pack_id": BUILTIN_PAYMENT_ID},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["style_pack"]["builtin"] is True
    assert body["style_pack"]["id"] == BUILTIN_PAYMENT_ID
    assert any(s["step_name"] == "load_style_context" for s in body["trace"]["steps"])

    replayed = client.get(f"/api/v1/runs/{body['run_id']}")
    assert replayed.status_code == 200
    assert replayed.json()["style_pack"]["id"] == BUILTIN_PAYMENT_ID
    assert replayed.json()["style_pack"]["builtin"] is True


def test_generate_without_style_pack_id_returns_null_snapshot(client: TestClient) -> None:
    response = client.post(
        "/api/v1/case-drafts/generate",
        data={"text": "登录"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "style_pack" in body
    assert body["style_pack"] is None
    assert all(s["step_name"] != "load_style_context" for s in body["trace"]["steps"])


def test_generate_unknown_style_pack_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/case-drafts/generate",
        data={"text": "登录", "style_pack_id": "00000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 400
    assert response.json()["issues"][0]["code"] == "PACK_NOT_FOUND"


def test_generate_invalid_style_pack_id_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/case-drafts/generate",
        data={"text": "登录", "style_pack_id": "abc"},
    )
    assert response.status_code == 400
    assert response.json()["issues"][0]["code"] == "INVALID_INPUT"
