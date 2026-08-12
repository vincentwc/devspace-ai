import os

from fastapi.testclient import TestClient

from devspace_ai.apps.api.main import create_app
from devspace_ai.infrastructure.config.settings import Settings


def test_health_and_ready() -> None:
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai",
    )
    app = create_app(settings=Settings(_env_file=None, database_url=db_url))
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200
