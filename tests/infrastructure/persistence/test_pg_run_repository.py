import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from devspace_ai.domain.run.models import GenerationRun, Issue, RunStatus
from devspace_ai.infrastructure.persistence.models import GenerationRunRow
from devspace_ai.infrastructure.persistence.pg_run_repository import PgRunRepository
from devspace_ai.infrastructure.style_pack.builtins import BUILTIN_PAYMENT_ID, get_builtin


@pytest.fixture()
def db_url():
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai_test",
    )
    return url


@pytest.fixture()
def repo(db_url):
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS style_packs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS generation_runs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    return PgRunRepository(db_url)


def test_save_and_get(repo):
    run = GenerationRun.start("req")
    run.finish(RunStatus.FAILED, [], [Issue(code="NO_VALID_DRAFTS", message="none")])
    repo.save(run)
    loaded = repo.get(run.run_id)
    assert loaded is not None
    assert loaded.status == RunStatus.FAILED
    assert loaded.issues[0].code == "NO_VALID_DRAFTS"


def test_save_and_get_style_pack_snapshot(repo):
    pack = get_builtin(BUILTIN_PAYMENT_ID)
    assert pack is not None
    run = GenerationRun.start("req")
    run.style_pack = pack
    run.finish(RunStatus.SUCCEEDED, [], [])
    repo.save(run)
    loaded = repo.get(run.run_id)
    assert loaded is not None
    assert loaded.style_pack is not None
    assert loaded.style_pack.id == BUILTIN_PAYMENT_ID
    assert loaded.style_pack.key == pack.key
    assert loaded.style_pack.name == pack.name
    assert loaded.style_pack.description == pack.description
    assert loaded.style_pack.builtin is True
    assert len(loaded.style_pack.examples) == len(pack.examples)
    assert loaded.style_pack.draft_count() == pack.draft_count()


def test_old_payload_without_style_pack_key_deserializes(repo, db_url):
    run_id = str(uuid4())
    engine = create_engine(db_url)
    with Session(engine) as session:
        session.add(
            GenerationRunRow(
                run_id=run_id,
                status=RunStatus.SUCCEEDED.value,
                created_at=datetime.now(UTC),
                input_text="legacy",
                payload={"drafts": [], "trace": {"steps": []}, "issues": [], "error": None},
            )
        )
        session.commit()
    loaded = repo.get(run_id)
    assert loaded is not None
    assert loaded.style_pack is None
    assert loaded.model is None


def test_save_and_get_model(repo):
    run = GenerationRun.start("req")
    run.model = "deepseek-chat"
    run.finish(RunStatus.SUCCEEDED, [], [])
    repo.save(run)
    loaded = repo.get(run.run_id)
    assert loaded is not None
    assert loaded.model == "deepseek-chat"
