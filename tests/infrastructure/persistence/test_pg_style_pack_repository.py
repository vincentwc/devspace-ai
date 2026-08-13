import json
import os
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.errors import StylePackError
from devspace_ai.domain.style_pack.models import StyleExample, StylePack
from devspace_ai.infrastructure.persistence.pg_style_pack_repository import (
    PgStylePackRepository,
)


@pytest.fixture()
def db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai_test",
    )


@pytest.fixture()
def repo(db_url: str) -> PgStylePackRepository:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS style_packs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS generation_runs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    return PgStylePackRepository(db_url)


def _pack(key: str = "cdp.payment.api") -> StylePack:
    return StylePack(
        id=str(uuid4()),
        key=key,
        name="支付接口",
        examples=[
            StyleExample(
                label="退款",
                requirement_text="用户申请退款",
                drafts=[
                    CaseDraft(
                        title="原路退款",
                        steps=[TestStep(action="点退款", expected="成功", test_data="1")],
                    )
                ],
            )
        ],
    )


def test_create_get_delete_count(repo: PgStylePackRepository) -> None:
    created = repo.create(_pack())
    loaded = repo.get(created.id)
    assert loaded is not None
    assert loaded.key == "cdp.payment.api"
    assert loaded.examples[0].requirement_text == "用户申请退款"
    assert repo.count() == 1
    with pytest.raises(StylePackError) as ei:
        repo.create(_pack())
    assert ei.value.code == "DUPLICATE_KEY"
    assert repo.delete(created.id) is True
    assert repo.get(created.id) is None
    assert repo.count() == 0


def _insert_corrupt_row(db_url: str, pack_id: str, key: str = "corrupt.pack") -> None:
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
                "key": key,
                "name": "损坏包",
                "examples": json.dumps([{"drafts": []}]),
            },
        )


def test_list_user_skips_crash_on_corrupt_json(repo: PgStylePackRepository, db_url: str) -> None:
    good = repo.create(_pack("good.pack"))
    corrupt_id = str(uuid4())
    _insert_corrupt_row(db_url, corrupt_id)
    packs = repo.list_user()
    by_id = {p.id: p for p in packs}
    assert good.id in by_id
    assert by_id[good.id].examples[0].requirement_text == "用户申请退款"
    assert corrupt_id in by_id
    assert by_id[corrupt_id].examples == []
    assert by_id[corrupt_id].draft_count() == 0


def test_get_corrupt_json_raises_invalid_example(repo: PgStylePackRepository, db_url: str) -> None:
    pack_id = str(uuid4())
    _insert_corrupt_row(db_url, pack_id)
    with pytest.raises(StylePackError) as ei:
        repo.get(pack_id)
    assert ei.value.code == "INVALID_EXAMPLE"


def test_create_integrity_error_maps_to_duplicate_key(repo: PgStylePackRepository) -> None:
    repo.create(_pack("race.key"))
    repo.get_by_key = lambda key: None  # type: ignore[method-assign]
    with pytest.raises(StylePackError) as ei:
        repo.create(_pack("race.key"))
    assert ei.value.code == "DUPLICATE_KEY"
