"""Integration assertions which SQLite's storage model cannot validate."""

import os
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from app.database import SessionLocal, engine
from app.models import AnalysisRun, Holding, Portfolio

pytestmark = pytest.mark.skipif(
    not os.getenv("QUANTLENS_TEST_DATABASE_URL"), reason="PostgreSQL integration only"
)


def test_postgres_numeric_precision_and_foreign_key_cascades(client, account):
    headers, portfolio_id = account
    base = f"/api/v1/portfolios/{portfolio_id}"
    added = client.post(
        base + "/holdings",
        headers=headers,
        json={"instrument_id": "BHARTIARTL.NS", "quantity": "1.123456", "average_cost": "1234.567891"},
    )
    assert added.status_code == 201
    with SessionLocal() as db:
        holding = db.get(Holding, added.json()["id"])
        assert holding.quantity == Decimal("1.123456")
        assert holding.average_cost == Decimal("1234.567891")
    assert client.post(base + "/analyses", headers=headers).status_code == 201
    assert client.delete(base, headers=headers).status_code == 204
    with SessionLocal() as db:
        assert db.get(Portfolio, portfolio_id) is None
        assert db.scalar(select(Holding.id).where(Holding.portfolio_id == portfolio_id)) is None
        assert db.scalar(select(AnalysisRun.id).where(AnalysisRun.portfolio_id == portfolio_id)) is None


def test_postgres_stores_analysis_as_json_and_timestamps_with_timezone(client, account):
    headers, portfolio_id = account
    saved = client.post(f"/api/v1/portfolios/{portfolio_id}/analyses", headers=headers)
    assert saved.status_code == 201
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT payload->>'data_mode', created_at FROM analysis_runs WHERE id=:id"),
            {"id": saved.json()["id"]},
        ).one()
        assert row[0] == "synthetic"
        assert row[1].tzinfo is not None
