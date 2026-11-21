from uuid import uuid4

import pytest


def test_authenticated_workflow(client):
    email = f"test-{uuid4().hex}@example.com"
    body = {"email": email, "password": "a-strong-password", "name": "Test student"}
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 409
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"}).status_code
        == 401
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": body["password"]}).status_code
        == 200
    )
    portfolio = client.post("/api/v1/portfolios", headers=headers, json={"name": "My portfolio"}).json()
    base = f"/api/v1/portfolios/{portfolio['id']}"
    assert client.get(base + "/summary", headers=headers).json()["holdings"] == []
    holding = {"instrument_id": "TCS.NS", "quantity": 2, "average_cost": 3000}
    added = client.post(base + "/holdings", headers=headers, json=holding)
    assert added.status_code == 201
    assert client.post(base + "/holdings", headers=headers, json=holding).status_code == 409
    summary = client.get(base + "/summary", headers=headers).json()
    assert summary["invested"] == 6000
    assert summary["value"] > 0
    assert summary["data_mode"] == "synthetic"
    assert summary["metrics"]["observations"] == 252
    assert (
        client.patch(
            base + "/holdings/" + added.json()["id"], headers=headers, json={**holding, "quantity": 3}
        ).status_code
        == 200
    )
    assert client.get(base + "/summary", headers=headers).json()["invested"] == 9000
    assert client.delete(base + "/holdings/" + added.json()["id"], headers=headers).status_code == 204
    assert client.delete(base, headers=headers).status_code == 204
    assert client.get(base + "/summary", headers=headers).status_code == 404
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_cross_user_access_is_blocked(client, account):
    first_headers, portfolio_id = account
    other = client.post("/api/v1/auth/demo").json()
    headers = {"Authorization": f"Bearer {other['access_token']}"}
    base = f"/api/v1/portfolios/{portfolio_id}"
    for suffix in ["/summary", "/reports", "/export.csv", "/export.pdf"]:
        assert client.get(base + suffix, headers=headers).status_code == 404
    assert client.post(base + "/forecasts", headers=headers).status_code == 404
    assert client.delete(base, headers=headers).status_code == 404
    own_holding = client.get(base + "/summary", headers=first_headers).json()["holdings"][0]
    other_portfolio = client.get("/api/v1/portfolios", headers=headers).json()[0]["id"]
    assert (
        client.delete(
            f"/api/v1/portfolios/{other_portfolio}/holdings/{own_holding['id']}", headers=headers
        ).status_code
        == 404
    )


def test_risk_scenarios_forecasts_exports_and_snapshots(client, account):
    headers, ident = account
    base = f"/api/v1/portfolios/{ident}"
    summary = client.get(base + "/summary", headers=headers).json()
    result = client.post(base + "/stress-tests", headers=headers, json={"shock": -0.1})
    assert result.status_code == 200
    assert result.json()["after"] == pytest.approx(summary["value"] * 0.9)
    forecast = client.post(base + "/forecasts", headers=headers)
    assert forecast.status_code == 200
    assert len(forecast.json()["models"]) == 3
    saved = client.post(base + "/analyses", headers=headers)
    assert saved.status_code == 201
    original = client.get(base + "/reports/" + saved.json()["id"], headers=headers).json()["payload"]
    h = summary["holdings"][0]
    client.patch(
        base + "/holdings/" + h["id"],
        headers=headers,
        json={"instrument_id": h["instrument_id"], "quantity": 1, "average_cost": 1},
    )
    assert client.get(base + "/reports/" + saved.json()["id"], headers=headers).json()["payload"] == original
    assert len(client.get(base + "/reports", headers=headers).json()) == 3
    assert "data_mode" in client.get(base + "/export.csv", headers=headers).text
    pdf = client.get(base + "/export.pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_market_failure_does_not_switch_sources(client, account, monkeypatch):
    headers, ident = account

    def fail(_):
        raise ValueError("Simulated provider failure")

    monkeypatch.setattr("app.syncing.fetch_yahoo", fail)
    base = f"/api/v1/portfolios/{ident}"
    assert client.post(base + "/data-refreshes", headers=headers).status_code == 502
    assert client.get(base + "/summary", headers=headers).json()["data_mode"] == "synthetic"


def test_csv_validation_and_import(client, account):
    headers, ident = account
    base = f"/api/v1/portfolios/{ident}"
    path = base + "/prices/import"
    assert (
        client.post(
            path, headers=headers, json={"instrument_id": "TCS.NS", "csv_text": "wrong,columns\n1,2"}
        ).status_code
        == 422
    )
    valid = "date,close,adjusted_close\n2025-01-02,100,99\n2025-01-03,102,101"
    assert (
        client.post(path, headers=headers, json={"instrument_id": "TCS.NS", "csv_text": valid}).json()["rows"]
        == 2
    )
    assert (
        client.post(path, headers=headers, json={"instrument_id": "TCS.NS", "csv_text": valid}).json()["rows"]
        == 2
    )
    assert client.get(base + "/summary", headers=headers).json()["data_mode"] == "synthetic"


@pytest.mark.parametrize(
    "body",
    [
        {"instrument_id": "TCS.NS", "quantity": 0, "average_cost": 100},
        {"instrument_id": "TCS.NS", "quantity": -2, "average_cost": 100},
        {"instrument_id": "UNKNOWN", "quantity": 1, "average_cost": 100},
    ],
)
def test_holding_validation(client, account, body):
    headers, ident = account
    assert client.post(f"/api/v1/portfolios/{ident}/holdings", headers=headers, json=body).status_code == 422


def test_authentication_required(client):
    assert client.get("/api/v1/portfolios").status_code == 401
    assert client.get("/api/v1/instruments/search").status_code == 401


def test_csv_prices_are_private_to_the_portfolio(client, account):
    headers, ident = account
    valid = "date,close,adjusted_close\n2025-01-02,100,99\n2025-01-03,102,101"
    path = f"/api/v1/portfolios/{ident}/prices/import"
    assert (
        client.post(path, headers=headers, json={"instrument_id": "TCS.NS", "csv_text": valid}).status_code
        == 200
    )
    assert (
        len(
            client.get(
                f"/api/v1/instruments/TCS.NS/prices?source=csv&portfolio_id={ident}", headers=headers
            ).json()["prices"]
        )
        == 2
    )
    other = client.post("/api/v1/auth/demo").json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert (
        client.get(
            f"/api/v1/instruments/TCS.NS/prices?source=csv&portfolio_id={ident}", headers=other_headers
        ).status_code
        == 404
    )
    assert client.get("/api/v1/instruments/TCS.NS/prices?source=csv", headers=headers).status_code == 422


def test_source_switch_rejects_incomplete_prices(client, account):
    headers, ident = account
    response = client.patch(
        f"/api/v1/portfolios/{ident}", headers=headers, json={"name": "Long-term equity", "data_mode": "csv"}
    )
    assert response.status_code == 409
    assert (
        client.get(f"/api/v1/portfolios/{ident}/summary", headers=headers).json()["data_mode"] == "synthetic"
    )


def test_instrument_history_has_source_and_dates(client, account):
    headers, _ = account
    response = client.get("/api/v1/instruments/TCS.NS/prices?source=synthetic", headers=headers)
    assert response.status_code == 200
    history = response.json()
    assert history["source"] == "synthetic"
    assert len(history["prices"]) == 252
    assert history["prices"][0]["date"] < history["prices"][-1]["date"]


def test_health_reports_database_unavailability_without_exposing_details(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def fail():
        raise OperationalError("private database address", {}, Exception("private connection detail"))

    assert client.get("/health").json()["status"] == "ok"
    monkeypatch.setattr("app.main.engine.connect", fail)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "service": "quantlens"}
    assert "private" not in response.text
