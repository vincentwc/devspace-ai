import os

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from devspace_ai.domain.run.models import GenerationRun, Issue, RunStatus
from devspace_ai.infrastructure.persistence.pg_run_repository import PgRunRepository


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
