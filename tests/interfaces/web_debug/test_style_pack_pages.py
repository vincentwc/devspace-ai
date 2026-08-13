import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from devspace_ai.apps.api.main import create_app
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.style_pack.builtins import BUILTIN_PAYMENT_ID

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


def test_style_pack_list_shows_builtins(client: TestClient) -> None:
    r = client.get("/debug/style-packs")
    assert r.status_code == 200
    assert "系统示例" in r.text
    assert "example.payment.api" in r.text
    assert "用此示例创建" in r.text


def test_generate_form_has_builtin_options(client: TestClient) -> None:
    r = client.get("/debug/")
    assert r.status_code == 200
    assert "用例风格" in r.text
    assert "00000000-0000-4000-8000-000000000001" in r.text


def test_generate_with_builtin_shows_trace(client: TestClient) -> None:
    r = client.post(
        "/debug/generate",
        data={
            "text": "用户申请退款",
            "style_pack_id": "00000000-0000-4000-8000-000000000001",
        },
    )
    assert r.status_code == 200
    assert "load_style_context" in r.text or "example.payment.api" in r.text


def test_copy_from_builtin_prefill(client: TestClient) -> None:
    r = client.get("/debug/style-packs/new?from=00000000-0000-4000-8000-000000000001")
    assert r.status_code == 200
    assert "副本" in r.text


def test_list_splits_system_and_user_packs(client: TestClient) -> None:
    created = client.post("/api/v1/style-packs", json=VALID_POST_BODY)
    assert created.status_code == 201
    user_id = created.json()["id"]

    r = client.get("/debug/style-packs")
    assert r.status_code == 200
    assert "我的风格包" in r.text
    assert r.text.index("系统示例") < r.text.index("我的风格包")
    assert "查看" in r.text
    assert f"/debug/style-packs/new?from={BUILTIN_PAYMENT_ID}" in r.text
    assert f"/debug/style-packs/{BUILTIN_PAYMENT_ID}/edit" not in r.text
    assert "新建" in r.text
    assert f"/debug/style-packs/{user_id}/edit" in r.text
    assert "删除" in r.text


def test_view_builtin_pack(client: TestClient) -> None:
    r = client.get(f"/debug/style-packs/{BUILTIN_PAYMENT_ID}")
    assert r.status_code == 200
    assert "示例 · 支付接口" in r.text
    assert "example.payment.api" in r.text
    assert "用户已支付成功" in r.text


def test_new_form_blank(client: TestClient) -> None:
    r = client.get("/debug/style-packs/new")
    assert r.status_code == 200
    assert "名称" in r.text
    assert "代号" in r.text


def test_edit_builtin_redirects_to_copy(client: TestClient) -> None:
    r = client.get(
        f"/debug/style-packs/{BUILTIN_PAYMENT_ID}/edit",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == f"/debug/style-packs/new?from={BUILTIN_PAYMENT_ID}"


def test_edit_user_pack_form(client: TestClient) -> None:
    created = client.post("/api/v1/style-packs", json=VALID_POST_BODY)
    assert created.status_code == 201
    user_id = created.json()["id"]

    r = client.get(f"/debug/style-packs/{user_id}/edit")
    assert r.status_code == 200
    assert "支付接口" in r.text
    assert "cdp.payment.api" in r.text
    assert "readonly" in r.text or "disabled" in r.text


def test_copy_from_builtin_empty_key(client: TestClient) -> None:
    r = client.get(f"/debug/style-packs/new?from={BUILTIN_PAYMENT_ID}")
    assert r.status_code == 200
    assert "示例 · 支付接口（副本）" in r.text
    assert 'id="key"' in r.text
    assert 'value="example.payment.api"' not in r.text
    assert "用户已支付成功" in r.text


def test_nav_link_on_style_pack_pages(client: TestClient) -> None:
    r = client.get("/debug/style-packs")
    assert r.status_code == 200
    assert 'href="/debug/style-packs"' in r.text
    assert "风格包" in r.text


def test_form_includes_structured_controls(client: TestClient) -> None:
    r = client.get("/debug/style-packs/new")
    assert r.status_code == 200
    assert "addExample" in r.text or "添加需求" in r.text
    assert "rationale" in r.text.lower() or "<details" in r.text
    assert "/api/v1/style-packs" in r.text or "style_pack_form.js" in r.text


def test_form_js_disables_save_until_fetch_settles() -> None:
    js = (
        Path(__file__).resolve().parents[3]
        / "src/devspace_ai/interfaces/web_debug/static/style_pack_form.js"
    ).read_text(encoding="utf-8")
    assert "disabled = true" in js
    assert "disabled = false" in js
