import os

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from devspace_ai.apps.api.main import create_app
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.style_pack.builtins import (
    BUILTIN_MARKETING_ID,
    BUILTIN_PAYMENT_ID,
)

VALID_POST_BODY = {
    "key": "cdp.payment.api",
    "name": "支付接口",
    "description": None,
    "examples": [
        {
            "label": "退款成功",
            "requirement_text": "用户申请全额退款",
            "drafts": [
                {
                    "title": "原路退款成功",
                    "preconditions": ["已支付"],
                    "steps": [{"action": "点退款", "expected": "成功", "test_data": "100"}],
                    "priority": "P1",
                    "tags": ["pay"],
                    "rationale": None,
                }
            ],
        }
    ],
}


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
    assert "当前模型：Fake" in r.text
    assert "忽略风格包范文" in r.text


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


def test_nav_includes_style_pack_link(client: TestClient) -> None:
    r = client.get("/debug/")
    assert r.status_code == 200
    assert 'href="/debug/style-packs"' in r.text
    assert "风格包" in r.text


def test_generate_dropdown_builtins_then_user_packs(client: TestClient) -> None:
    created = client.post("/api/v1/style-packs", json=VALID_POST_BODY)
    assert created.status_code == 201
    user_id = created.json()["id"]

    r = client.get("/debug/")
    assert r.status_code == 200
    assert "<select" in r.text
    assert 'name="style_pack_id"' in r.text
    assert 'value=""' in r.text
    assert "示例 · 支付接口（example.payment.api）" in r.text
    assert "示例 · 营销活动页（example.marketing.web）" in r.text
    assert "支付接口（cdp.payment.api）" in r.text
    assert r.text.index(BUILTIN_PAYMENT_ID) < r.text.index(BUILTIN_MARKETING_ID)
    assert r.text.index(BUILTIN_MARKETING_ID) < r.text.index(user_id)


def test_generate_failed_redisplays_selected_style_pack(client: TestClient) -> None:
    r = client.post(
        "/debug/generate",
        data={"text": "", "style_pack_id": BUILTIN_PAYMENT_ID},
    )
    assert r.status_code == 400
    assert f'value="{BUILTIN_PAYMENT_ID}"' in r.text
    assert "selected" in r.text


def test_run_detail_shows_style_pack_name(client: TestClient) -> None:
    r = client.post(
        "/debug/generate",
        data={"text": "用户申请退款", "style_pack_id": BUILTIN_PAYMENT_ID},
    )
    assert r.status_code == 200
    assert "风格包：示例 · 支付接口（example.payment.api）" in r.text
    assert "模型：fake" in r.text


def test_generate_form_shows_real_model_name(db_url: str) -> None:
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
        app_env="local",
        database_url=db_url,
        model_provider="openai_compatible",
        model_api_key="sk-test",
        model_base_url="https://example.com/v1",
        model_name="deepseek-chat",
        max_text_chars=1_000,
    )
    client = TestClient(create_app(settings=settings))
    r = client.get("/debug/")
    assert r.status_code == 200
    assert "当前模型：deepseek-chat" in r.text
    assert "会注入风格包" in r.text
    assert "当前模型：Fake" not in r.text
