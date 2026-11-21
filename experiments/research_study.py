"""Reproduce three retrospective current-weight portfolio volatility experiments.
Run from backend with uv run python ../experiments/research_study.py.
Downloads are private ignored artifacts, not bundled or redistributed datasets.
"""

import argparse, json, secrets, sys
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import numpy as np
import pandas as pd
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.bootstrap import bootstrap_database
from app.database import SessionLocal
from app.market import fetch_yahoo, replace_history, seed_catalog
from app.models import User, Portfolio, Holding
from app.security import passwords
from app.services import portfolio_data
from app.analytics.forecasting import evaluate

SYMBOLS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "ITC.NS"]
GROUPS = {
    "Diversified six": SYMBOLS,
    "Technology pair": ["TCS.NS", "INFY.NS"],
    "Banking pair": ["HDFCBANK.NS", "ICICIBANK.NS"],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-window", type=int, default=504)
    parser.add_argument("--test-days", type=int, default=252)
    args = parser.parse_args()
    if args.training_window < 252 or not 1 <= args.test_days <= 252:
        parser.error("Use >=252 training returns and 1–252 target days.")
    root = Path(__file__).resolve().parent / "results"
    root.mkdir(parents=True, exist_ok=True)
    frames = {}
    for symbol in SYMBOLS + ["^NSEI"]:
        cache = root / (symbol.replace("^", "") + "-history.csv")
        if cache.exists():
            frame = pd.read_csv(cache, index_col=0)
            frame.index = pd.Index(pd.to_datetime(frame.index).date)
        else:
            frame = fetch_yahoo(symbol)
            frame.to_csv(cache)
        frames[symbol] = frame
        print(symbol, len(frame), str(frame.index.min()), str(frame.index.max()), flush=True)
    common = set.intersection(*(set(f.index) for f in frames.values()))
    dates = sorted(common)
    if len(dates) < args.training_window + args.test_days + 1:
        raise ValueError("Insufficient shared dates.")
    # Fixed shared dates ensure model comparisons use the same target observations.
    dates = dates[-(args.training_window + args.test_days + 1) :]
    now = datetime.now(timezone.utc).isoformat()
    password = secrets.token_urlsafe(24)
    email = "study-" + secrets.token_hex(5) + "@example.com"
    manifest = {
        "generated_at": now,
        "source": "Yahoo Finance via yfinance",
        "dataset_start": str(dates[0]),
        "dataset_end": str(dates[-1]),
        "training_window": args.training_window,
        "test_days": args.test_days,
        "studies": [],
        "limitations": [
            "Current weights selected retrospectively; no investable strategy backtest.",
            "Squared daily returns are a noisy variance proxy.",
            "Three illustrative portfolios do not establish general model superiority.",
            "Yahoo availability and revised adjustments may change later reruns.",
        ],
    }
    bootstrap_database()
    with SessionLocal() as db:
        seed_catalog(db)
        user = User(name="Research demonstration", email=email, password_hash=passwords.hash(password))
        db.add(user)
        db.flush()
        for symbol, frame in frames.items():
            replace_history(db, symbol, frame, "yahoo")
        for name, symbols in GROUPS.items():
            portfolio = Portfolio(
                user_id=user.id, name=name, data_mode="yahoo", last_sync_at=datetime.now(timezone.utc)
            )
            db.add(portfolio)
            db.flush()
            for symbol in symbols:
                price = Decimal(str(float(frames[symbol].loc[dates[-1], "Close"])))
                db.add(
                    Holding(
                        portfolio_id=portfolio.id,
                        instrument_id=symbol,
                        quantity=(Decimal("100000") / len(symbols) / price).quantize(Decimal("0.000001")),
                        average_cost=(price * Decimal("0.9")).quantize(Decimal("0.000001")),
                    )
                )
            db.flush()
            summary, _ = portfolio_data(db, portfolio, lookback=252)
            weights = np.array(
                [
                    next(h["weight"] for h in summary["holdings"] if h["instrument_id"] == sym)
                    for sym in symbols
                ]
            )
            prices = pd.DataFrame({sym: frames[sym].loc[dates, "Adj Close"] for sym in symbols})
            returns = prices.pct_change(fill_method=None).dropna() @ weights
            result = evaluate(
                returns.to_numpy(),
                args.training_window,
                args.test_days,
                on_progress=lambda done, total: (
                    print(f"{name}: {done}/{total}", flush=True) if done % 63 == 0 else None
                ),
            )
            result.update(
                {
                    "name": name,
                    "portfolio_id": portfolio.id,
                    "data_mode": "yahoo",
                    "as_of": str(dates[-1]),
                    "generated_at": now,
                    "holdings": summary["holdings"],
                    "summary": summary,
                    "return_dates": [str(d) for d in returns.index],
                    "return_values": returns.tolist(),
                    "evaluation_dates": [str(d) for d in returns.index[-args.test_days :]],
                    "methodology": summary["methodology"],
                    "selection": "Equal current value weights at the shared final price date. Illustrative average costs set at 90% of that close; P&L is not an investment result.",
                    "limitations": manifest["limitations"],
                }
            )
            path = root / (name.lower().replace(" ", "-") + ".json")
            path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
            manifest["studies"].append(
                {
                    "name": name,
                    "portfolio_id": portfolio.id,
                    "file": path.name,
                    "metrics": result["metrics"],
                    "risk": summary["metrics"],
                    "evaluation_start": result["evaluation_dates"][0],
                    "evaluation_end": result["evaluation_dates"][-1],
                }
            )
            print(name, json.dumps(result["metrics"]), flush=True)
        db.commit()
    credential = root / "study-login.json"
    credential.write_text(json.dumps({"email": email, "password": password}))
    credential.chmod(0o600)
    (root / "study-manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print("Saved private study inputs and results to", root, flush=True)


if __name__ == "__main__":
    main()
