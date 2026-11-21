"""Run from backend: uv run python ../experiments/evaluate.py --portfolio ID --test-days 60.

Evaluates fixed current weights retrospectively; it does not backtest an investable historical strategy.
No provider calls are made. The portfolio's persisted source is used and recorded in the output.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.analytics.forecasting import evaluate  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Portfolio  # noqa: E402
from app.services import portfolio_data  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", required=True)
    parser.add_argument("--training-window", type=int, default=504)
    parser.add_argument("--test-days", type=int, default=60)
    parser.add_argument("--output", default="../experiments/results/evaluation.json")
    args = parser.parse_args()
    if args.training_window < 252 or not 1 <= args.test_days <= 252:
        parser.error("Use a training window of at least 252 returns and 1–252 test days.")
    with SessionLocal() as db:
        p = db.get(Portfolio, args.portfolio)
        if not p:
            parser.error("Portfolio not found in the configured database.")
        data, returns = portfolio_data(db, p, args.training_window + args.test_days)
        if returns is None:
            parser.error("The portfolio has no holdings.")
        result = evaluate(returns.to_numpy(), args.training_window, args.test_days)
        result.update(
            {
                "portfolio_id": p.id,
                "data_mode": p.data_mode,
                "as_of": data["as_of"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "holdings": data["holdings"],
                "methodology": data["methodology"],
                "return_dates": [str(d) for d in returns.index],
                "return_values": returns.tolist(),
                "evaluation_dates": [str(d) for d in returns.index[-args.test_days :]],
                "limitation": "Squared daily returns are a noisy variance proxy. Current holdings and weights are selected retrospectively. Synthetic observations cannot support empirical market conclusions.",
            }
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["metrics"], indent=2))
    print(f"Saved reproducible inputs, forecasts and metrics to {output.resolve()}")


if __name__ == "__main__":
    main()
