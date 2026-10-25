import warnings

import numpy as np
from arch import arch_model


def forecast(returns, horizon=5):
    r = np.asarray(returns, dtype=float)
    if len(r) < 252 or not np.isfinite(r).all():
        raise ValueError("Forecasting requires at least 252 aligned daily returns.")
    if np.std(r) < 1e-10:
        raise ValueError("Forecasting is unavailable for a constant return series.")
    variance = float(np.var(r[: min(60, len(r))], ddof=1))
    for value in r:
        variance = 0.94 * variance + 0.06 * value**2
    baseline = float(np.mean(r[-60:] ** 2))
    # Both models assume a zero conditional mean. arch uses percentage returns for numerical stability.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = arch_model(r * 100, mean="Zero", vol="GARCH", p=1, q=1, rescale=False).fit(
            disp="off", show_warning=False, options={"maxiter": 500}
        )
    if fit.convergence_flag != 0:
        raise ValueError("GARCH did not converge. Try another lookback period or portfolio.")
    garch = fit.forecast(horizon=horizon, reindex=False).variance.iloc[-1].to_numpy() / 10000
    return {
        "horizon": horizon,
        "observations": len(r),
        "unit": "annualized volatility (decimal)",
        "mean_assumption": "zero",
        "ewma_lambda": 0.94,
        "models": {
            "Historical (60d)": [float(np.sqrt(baseline * 252))] * horizon,
            "EWMA": [float(np.sqrt(variance * 252))] * horizon,
            "GARCH(1,1)": [float(np.sqrt(max(v, 0) * 252)) for v in garch],
        },
        "variance_forecasts": {
            "Historical (60d)": [baseline] * horizon,
            "EWMA": [variance] * horizon,
            "GARCH(1,1)": garch.tolist(),
        },
        "parameters": {str(k): float(v) for k, v in fit.params.items()},
        "warning": "Forecasts estimate variability, not future stock prices or investment returns.",
    }


def evaluate(returns, training_window=504, test_days=60):
    """Strict rolling one-day-ahead experiment, using squared returns as a noisy variance proxy."""
    r = np.asarray(returns, dtype=float)
    if len(r) < training_window + test_days:
        raise ValueError("Insufficient observations for the requested training and evaluation windows.")
    predictions = {name: [] for name in ["Historical (60d)", "EWMA", "GARCH(1,1)"]}
    targets = []
    for t in range(len(r) - test_days, len(r)):
        result = forecast(r[t - training_window : t], horizon=1)
        for name, values in result["variance_forecasts"].items():
            predictions[name].append(values[0])
        targets.append(r[t] ** 2)
    target = np.asarray(targets)
    scores = {}
    for name, values in predictions.items():
        h = np.maximum(np.asarray(values), 1e-12)
        scores[name] = {
            "mae": float(np.abs(h - target).mean()),
            "rmse": float(np.sqrt(np.square(h - target).mean())),
            "qlike": float((np.log(h) + target / h).mean()),
        }
    return {
        "training_window": training_window,
        "test_days": test_days,
        "mean_assumption": "zero",
        "target": "squared daily returns: noisy variance proxy",
        "scale": "decimal daily variance",
        "metrics": scores,
        "predictions": predictions,
        "targets": targets,
    }
