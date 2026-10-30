import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_temp = tempfile.TemporaryDirectory(prefix="quantlens-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_temp.name}/test.db"
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
