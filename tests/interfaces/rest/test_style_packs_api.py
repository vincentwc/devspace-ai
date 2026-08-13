import json
import os
from uuid import uuid4

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


def _migrate(db_url: str) -> None:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS style_packs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS generation_runs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


@pytest.fixture()
def client_write_on(db_url: str) -> TestClient:
    """夹具 A：app_env=local，写路由开启。"""
    _migrate(db_url)
    settings = Settings(
        _env_file=None,
        database_url=db_url,
        model_provider="fake",
        app_env="local",
    )
    return TestClient(create_app(settings=settings))


@pytest.fixture()
def client_write_off(db_url: str) -> TestClient:
    """夹具 B：prod + enable_debug_ui=False，写路由关闭。"""
    _migrate(db_url)
    settings = Settings(
        _env_file=None,
        database_url=db_url,
        model_provider="fake",
        app_env="prod",
        enable_debug_ui=False,
    )
    return TestClient(create_app(settings=settings))


def test_list_builtins_when_write_off(client_write_off: TestClient) -> None:
    response = client_write_off.get("/api/v1/style-packs")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    builtins = [p for p in items if p.get("builtin") is True]
    assert len(builtins) >= 2


def test_post_returns_404_when_write_off(client_write_off: TestClient) -> None:
    response = client_write_off.post("/api/v1/style-packs", json=VALID_POST_BODY)
    assert response.status_code == 404


def test_post_valid_pack_returns_201(client_write_on: TestClient) -> None:
    response = client_write_on.post("/api/v1/style-packs", json=VALID_POST_BODY)
    assert response.status_code == 201
    body = response.json()
    assert body["builtin"] is False
    assert body["key"] == "cdp.payment.api"
    assert body["name"] == "支付接口"
    assert "examples" in body
    assert body["requirement_count"] == 1
    assert body["draft_count"] == 1


def test_put_delete_builtin_returns_pack_readonly(client_write_on: TestClient) -> None:
    put_resp = client_write_on.put(
        f"/api/v1/style-packs/{BUILTIN_PAYMENT_ID}",
        json={
            "name": "改名",
            "description": None,
            "examples": VALID_POST_BODY["examples"],
        },
    )
    assert put_resp.status_code == 400
    assert put_resp.json()["issues"][0]["code"] == "PACK_READONLY"

    del_resp = client_write_on.delete(f"/api/v1/style-packs/{BUILTIN_MARKETING_ID}")
    assert del_resp.status_code == 400
    assert del_resp.json()["issues"][0]["code"] == "PACK_READONLY"


def test_get_unknown_id_returns_pack_not_found(client_write_on: TestClient) -> None:
    response = client_write_on.get("/api/v1/style-packs/00000000-0000-4000-8000-000000000099")
    assert response.status_code == 404
    assert response.json()["issues"][0]["code"] == "PACK_NOT_FOUND"


def test_post_reserved_key_returns_invalid_key(client_write_on: TestClient) -> None:
    body = {**VALID_POST_BODY, "key": "example.foo"}
    response = client_write_on.post("/api/v1/style-packs", json=body)
    assert response.status_code == 400
    assert response.json()["issues"][0]["code"] == "INVALID_KEY"


def _insert_corrupt_pack(db_url: str, pack_id: str) -> None:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO style_packs "
                "(id, key, name, description, examples, created_at, updated_at) "
                "VALUES (:id, :key, :name, NULL, CAST(:examples AS jsonb), now(), now())"
            ),
            {
                "id": pack_id,
                "key": "corrupt.pack",
                "name": "损坏包",
                "examples": json.dumps([{"drafts": []}]),
            },
        )


def test_list_survives_corrupt_user_pack(client_write_on: TestClient, db_url: str) -> None:
    pack_id = str(uuid4())
    _insert_corrupt_pack(db_url, pack_id)
    response = client_write_on.get("/api/v1/style-packs")
    assert response.status_code == 200
    items = response.json()
    builtins = [p for p in items if p.get("builtin") is True]
    assert len(builtins) >= 2
    corrupt = next(p for p in items if p["id"] == pack_id)
    assert corrupt["requirement_count"] == 0
    assert corrupt["draft_count"] == 0


def test_get_corrupt_pack_returns_invalid_example(client_write_on: TestClient, db_url: str) -> None:
    pack_id = str(uuid4())
    _insert_corrupt_pack(db_url, pack_id)
    response = client_write_on.get(f"/api/v1/style-packs/{pack_id}")
    assert response.status_code == 400
    assert response.json()["issues"][0]["code"] == "INVALID_EXAMPLE"
