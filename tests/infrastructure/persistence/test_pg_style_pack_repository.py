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
