import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

_temp = tempfile.TemporaryDirectory(prefix="quantlens-tests-")
test_database = os.getenv("QUANTLENS_TEST_DATABASE_URL", "")
if test_database:
    url = make_url(test_database)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise RuntimeError("PostgreSQL integration tests require a dedicated database ending in _test.")
os.environ["DATABASE_URL"] = test_database or f"sqlite:///{_temp.name}/test.db"
os.environ["SMTP_HOST"] = ""
os.environ["RATE_LIMITS_ENABLED"] = "false"
os.environ["SYNC_POLL_SECONDS"] = "3600"
os.environ["OUTBOX_DIR"] = f"{_temp.name}/outbox"
os.environ["JWT_SECRET"] = "test-only-secret-that-is-long-enough-for-hmac-verification"

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as instance:
        yield instance


@pytest.fixture
def account(client):
    response = client.post("/api/v1/auth/demo")
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    portfolio = client.get("/api/v1/portfolios", headers=headers).json()[0]
    return headers, portfolio["id"]
