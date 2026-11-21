import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.limiting import SlidingWindow
from app.models import PasswordReset, RefreshToken


def registration(client):
    body = {"email": f"qa-{uuid4().hex}@example.com", "name": "Quality check", "password": "OriginalPass123"}
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    return body, response.json()


def test_refresh_rotation_replay_revokes_session(client):
    _, initial = registration(client)
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": initial["refresh_token"]})
    assert refreshed.status_code == 200
    latest = refreshed.json()
    assert latest["refresh_token"] != initial["refresh_token"]
    with SessionLocal() as db:
        stored = db.scalars(select(RefreshToken)).all()
        assert all(token.token_hash != initial["refresh_token"] for token in stored)
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": initial["refresh_token"]}).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + latest["access_token"]}
        ).status_code
        == 401
    )


def test_password_recovery_uniform_response_expiry_and_revocation(client, monkeypatch):
    body, auth = registration(client)
    delivered = []
    monkeypatch.setattr("app.recovery.deliver", lambda email, code: delivered.append((email, code)))
    known = client.post("/api/v1/auth/password-reset/request", json={"email": body["email"]})
    unknown = client.post("/api/v1/auth/password-reset/request", json={"email": "missing-" + body["email"]})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert len(delivered) == 1
    code = delivered[0][1]
    reset = {"email": body["email"], "code": code, "password": "NewSecurePass123"}
    assert (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={**reset, "code": "00000000" if code != "00000000" else "11111111"},
        ).status_code
        == 400
    )
    assert client.post("/api/v1/auth/password-reset/confirm", json=reset).status_code == 200
    assert client.post("/api/v1/auth/password-reset/confirm", json=reset).status_code == 400
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": body["email"], "password": body["password"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": body["email"], "password": reset["password"]}
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + auth["access_token"]}).status_code
        == 401
    )
    client.post("/api/v1/auth/password-reset/request", json={"email": body["email"]})
    with SessionLocal() as db:
        row = db.scalar(select(PasswordReset).where(PasswordReset.user_id == auth["user"]["id"]))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert (
        client.post(
            "/api/v1/auth/password-reset/confirm", json={**reset, "code": delivered[-1][1]}
        ).status_code
        == 400
    )


def test_reset_attempt_limit(client, monkeypatch):
    body, _ = registration(client)
    codes = []
    monkeypatch.setattr("app.recovery.deliver", lambda _, code: codes.append(code))
    client.post("/api/v1/auth/password-reset/request", json={"email": body["email"]})
    wrong = "00000000" if codes[0] != "00000000" else "11111111"
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/password-reset/confirm",
                json={"email": body["email"], "code": wrong, "password": "NewPass1234"},
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"email": body["email"], "code": codes[0], "password": "NewPass1234"},
        ).status_code
        == 400
    )


def test_sliding_rate_limit_recovers_after_window():
    window = SlidingWindow()
    window.check("account", 2, 60, now=1)
    window.check("account", 2, 60, now=2)
    with pytest.raises(Exception) as error:
        window.check("account", 2, 60, now=3)
    assert error.value.status_code == 429
    window.check("account", 2, 60, now=63)


def test_benchmark_uses_common_price_returns(client, account):
    headers, ident = account
    response = client.get(f"/api/v1/portfolios/{ident}/summary", headers=headers)
    benchmark = response.json()["benchmark"]
    assert benchmark["available"] and benchmark["observations"] == 252
    assert len(benchmark["series"]) == 253
    assert benchmark["series"][0]["portfolio"] == benchmark["series"][0]["benchmark"] == 100
    assert benchmark["series"][-1]["portfolio"] / 100 - 1 == pytest.approx(benchmark["portfolio_return"])


def test_evaluation_is_saved_and_isolated(client, account):
    headers, ident = account
    base = f"/api/v1/portfolios/{ident}"
    created = client.post(
        base + "/evaluations", headers=headers, json={"training_window": 252, "test_days": 5}
    )
    assert created.status_code == 202
    evaluation_id = created.json()["id"]
    path = base + "/evaluations/" + evaluation_id
    for _ in range(100):
        detail = client.get(path, headers=headers).json()
        if detail["status"] not in ["queued", "running"]:
            break
        time.sleep(0.02)
    assert detail["status"] == "completed", detail
    assert detail["progress"] == 5 and set(detail["result"]["metrics"]) == {
        "EWMA",
        "GARCH(1,1)",
        "Historical (60d)",
    }
    assert len(detail["result"]["evaluation_dates"]) == 5
    other = client.post("/api/v1/auth/demo").json()
    assert client.get(path, headers={"Authorization": "Bearer " + other["access_token"]}).status_code == 404
    exported = client.get(path + "/export.json", headers=headers)
    assert exported.status_code == 200 and exported.json()["scale"] == "decimal daily variance"


def test_portfolio_comparison_and_sync_settings(client, account):
    headers, ident = account
    another = client.post("/api/v1/portfolios", headers=headers, json={"name": "Second"}).json()["id"]
    result = client.get(f"/api/v1/portfolio-comparison?ids={ident}&ids={another}", headers=headers)
    assert result.status_code == 200 and len(result.json()["portfolios"]) == 2
    assert (
        client.patch(
            f"/api/v1/portfolios/{ident}/settings", headers=headers, json={"auto_sync": True}
        ).status_code
        == 422
    )
    assert client.get(f"/api/v1/portfolios/{ident}/sync-history", headers=headers).json() == []


def test_csv_extreme_prices_are_rejected(client, account):
    headers, ident = account
    csv = "date,close,adjusted_close\n2025-01-02,1e300,1e300\n2025-01-03,1e300,1e300"
    assert (
        client.post(
            f"/api/v1/portfolios/{ident}/prices/import",
            headers=headers,
            json={"instrument_id": "TCS.NS", "csv_text": csv},
        ).status_code
        == 422
    )


def test_missing_prices_do_not_block_position_management(client, account):
    headers, ident = account
    added = client.post(
        f"/api/v1/portfolios/{ident}/holdings",
        headers=headers,
        json={"instrument_id": "TCS.BO", "quantity": "2", "average_cost": "1000"},
    ).json()
    positions = client.get(f"/api/v1/portfolios/{ident}/holdings", headers=headers)
    assert positions.status_code == 200 and any(h["id"] == added["id"] for h in positions.json())
    other = client.post("/api/v1/auth/demo").json()
    assert (
        client.get(
            f"/api/v1/portfolios/{ident}/holdings",
            headers={"Authorization": "Bearer " + other["access_token"]},
        ).status_code
        == 404
    )


def test_provider_ohlcv_persisted_but_never_invented(client, account):
    import pandas as pd

    from app.market import replace_history
    from app.models import PriceBar

    headers, _ = account
    frame = pd.DataFrame(
        {
            "Open": [99.0, 100.0],
            "High": [102.0, 103.0],
            "Low": [98.0, 99.0],
            "Close": [101.0, 102.0],
            "Adj Close": [100.0, 101.0],
            "Volume": [1000000, 2000000],
        },
        index=[datetime(2025, 1, 2).date(), datetime(2025, 1, 3).date()],
    )
    with SessionLocal() as db:
        replace_history(db, "TCS.NS", frame, "yahoo")
        db.commit()
        bar = db.scalar(
            select(PriceBar).where(PriceBar.instrument_id == "TCS.NS", PriceBar.source == "yahoo")
        )
        assert float(bar.open) == 99 and int(bar.volume) == 1000000
    response = client.get("/api/v1/instruments/TCS.NS/prices?source=yahoo", headers=headers)
    assert response.json()["prices"][-1]["high"] == 103
    synthetic = client.get("/api/v1/instruments/TCS.NS/prices?source=synthetic", headers=headers)
    assert synthetic.json()["prices"][-1]["volume"] is None


def test_automatic_sync_failure_keeps_prices_and_delays_retry(client, account, monkeypatch):
    from app.models import DataSyncRun, Portfolio
    from app.syncing import sync_due

    headers, ident = account
    calls = []
    with SessionLocal() as db:
        p = db.get(Portfolio, ident)
        p.data_mode = "yahoo"
        p.auto_sync = True
        db.commit()

    def failed(_):
        calls.append(1)
        raise ValueError("Provider test outage")

    monkeypatch.setattr("app.syncing.fetch_yahoo", failed)
    sync_due()
    sync_due()
    assert len(calls) == 1
    with SessionLocal() as db:
        runs = list(db.scalars(select(DataSyncRun).where(DataSyncRun.portfolio_id == ident)))
        assert len(runs) == 1 and runs[0].status == "failed"
        assert db.get(Portfolio, ident).last_sync_at is not None


def test_unavailable_evaluation_worker_does_not_leave_queued_job(client, account, monkeypatch):
    from app.models import ForecastEvaluation

    headers, ident = account
    monkeypatch.setattr("app.evaluations.executor", None)
    response = client.post(
        f"/api/v1/portfolios/{ident}/evaluations",
        headers=headers,
        json={"training_window": 252, "test_days": 5},
    )
    assert response.status_code == 503
    with SessionLocal() as db:
        assert (
            db.scalar(select(ForecastEvaluation.id).where(ForecastEvaluation.portfolio_id == ident)) is None
        )


def test_profile_updates_only_current_user(client):
    _, auth = registration(client)
    headers = {"Authorization": "Bearer " + auth["access_token"]}
    assert client.patch("/api/v1/auth/me", headers=headers, json={"name": "  "}).status_code == 422
    changed = client.patch("/api/v1/auth/me", headers=headers, json={"name": "Updated display"})
    assert changed.status_code == 200 and changed.json()["id"] == auth["user"]["id"]
    assert client.get("/api/v1/auth/me", headers=headers).json()["name"] == "Updated display"
