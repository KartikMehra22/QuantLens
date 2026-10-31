import numpy as np
import pandas as pd
import pytest

from app.analytics.forecasting import evaluate, forecast
from app.analytics.risk import diversification, metrics, stress


def test_first_observation_loss_is_in_drawdown():
    result = metrics(pd.Series([-0.1, *([0.0] * 19)]))
    assert result["max_drawdown"] == pytest.approx(0.1)
    assert result["cumulative_return"] == pytest.approx(-0.1)


def test_exact_empirical_tail_with_fractional_boundary():
    r = pd.Series([-0.1, -0.05, *([0.01] * 28)])
    result = metrics(r)
    assert result["var_95"] == pytest.approx(0.05)
    assert result["cvar_95"] == pytest.approx((0.1 + 0.5 * 0.05) / 1.5)


def test_risk_contributions_reconcile_to_portfolio_volatility():
    r = pd.DataFrame(np.random.default_rng(7).normal(0, 0.01, (300, 3)))
    w = np.array([0.2, 0.3, 0.5])
    result = diversification(r, w)
    total = np.sqrt(w @ r.cov().to_numpy() @ w) * np.sqrt(252)
    assert sum(x["volatility"] for x in result["contributions"]) == pytest.approx(total)
    assert sum(x["percentage"] for x in result["contributions"]) == pytest.approx(1)


def test_constant_returns_do_not_create_infinite_sharpe_or_correlations():
    assert metrics(pd.Series([0.0] * 30))["sharpe_ratio"] is None
    assert diversification(pd.DataFrame({"a": [0.0] * 30}), np.array([1.0]))["correlations"] == [[None]]


def test_asset_specific_shocks_reconcile():
    result = stress([1000, 2000], [-0.1, -0.2])
    assert result["after"] == 2500
    assert result["change"] == -500


@pytest.mark.parametrize("shocks", [[-1.01], [float("nan")], [0.1, 0.2]])
def test_invalid_shocks_are_rejected(shocks):
    with pytest.raises(ValueError):
        stress([100], shocks)


def test_forecast_variance_units_and_horizon():
    r = np.random.default_rng(20).normal(0, 0.012, 600)
    result = forecast(r, 5)
    assert len(result["models"]["GARCH(1,1)"]) == 5
    assert result["models"]["GARCH(1,1)"][0] == pytest.approx(
        np.sqrt(result["variance_forecasts"]["GARCH(1,1)"][0] * 252)
    )
    assert 0.00001 < result["variance_forecasts"]["GARCH(1,1)"][0] < 0.001


def test_evaluation_does_not_look_ahead():
    r = np.random.default_rng(42).normal(0, 0.012, 520)
    first = evaluate(r, 504, 3)
    changed = r.copy()
    changed[-1] = 0.4
    second = evaluate(changed, 504, 3)
    assert first["predictions"] == second["predictions"]
    assert first["targets"][-1] != second["targets"][-1]


def test_short_forecasts_fail_explicitly():
    with pytest.raises(ValueError, match="252"):
        forecast([0.01] * 20)
