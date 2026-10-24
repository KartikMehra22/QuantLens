"""Pure analytics functions. Returns are decimal simple returns; covariance is daily."""

import numpy as np
import pandas as pd


def finite(value):
    return float(value) if value is not None and np.isfinite(value) else None


def wealth_series(returns: pd.Series) -> pd.Series:
    return (1 + returns).cumprod()


def metrics(returns: pd.Series, annual_rf: float = 0.06, confidence: float = 0.95):
    values = returns.dropna().to_numpy(dtype=float)
    if len(values) < 20:
        return None
    sigma = np.std(values, ddof=1)
    # Include initial capital so a loss on the first day contributes to drawdown.
    wealth = np.r_[1.0, np.cumprod(1 + values)]
    drawdown = wealth / np.maximum.accumulate(wealth) - 1
    daily_rf = (1 + annual_rf) ** (1 / 252) - 1
    # Empirical inverse CDF and a fractional boundary observation define the worst 5% exactly.
    losses = np.sort(-values)[::-1]
    tail_size = len(values) * (1 - confidence)
    full = int(np.floor(tail_size + 1e-10))
    fraction = max(0, tail_size - full)
    tail_sum = losses[:full].sum() + (fraction * losses[full] if fraction > 1e-10 else 0)
    var = np.quantile(-values, confidence, method="inverted_cdf")
    return {
        "observations": len(values),
        "annualized_volatility": finite(sigma * np.sqrt(252)),
        "sharpe_ratio": finite(np.sqrt(252) * (values.mean() - daily_rf) / sigma) if sigma > 1e-12 else None,
        "max_drawdown": float(-drawdown.min()),
        "var_95": float(var),
        "cvar_95": float(tail_sum / tail_size),
        "cumulative_return": float(wealth[-1] - 1),
        "cagr": finite(wealth[-1] ** (252 / len(values)) - 1),
        "risk_free_rate": annual_rf,
    }


def diversification(returns: pd.DataFrame, weights: np.ndarray):
    covariance = returns.cov().to_numpy()
    sigma = float(np.sqrt(max(0, weights @ covariance @ weights)))
    contributions = weights * (covariance @ weights) / sigma if sigma > 1e-12 else np.zeros(len(weights))
    return {
        "correlations": [[finite(x) for x in row] for row in returns.corr().to_numpy()],
        "contributions": [
            {"volatility": float(rc * np.sqrt(252)), "percentage": float(rc / sigma) if sigma > 1e-12 else 0}
            for rc in contributions
        ],
        "concentration_hhi": float(weights @ weights),
    }


def stress(values: list[float], shocks: list[float]):
    if len(values) != len(shocks) or any(not np.isfinite(s) or s < -1 or s > 5 for s in shocks):
        raise ValueError("Shocks must be between -100% and +500% and match the holdings.")
    before = float(sum(values))
    changes = [float(v * s) for v, s in zip(values, shocks, strict=True)]
    return {
        "before": before,
        "after": before + sum(changes),
        "change": sum(changes),
        "change_pct": sum(changes) / before if before else 0,
        "holding_changes": changes,
    }
