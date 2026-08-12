from fastapi.testclient import TestClient

from devspace_ai.apps.api.main import create_app


def test_health_and_ready(tmp_path):
    app = create_app()
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200
