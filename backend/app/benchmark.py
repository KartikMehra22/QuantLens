import numpy as np
import pandas as pd
from sqlalchemy import select

from .models import PriceBar


def compare_benchmark(db, portfolio, ids, weights, raw, lookback):
    source = f"csv:{portfolio.id}" if portfolio.data_mode == "csv" else portfolio.data_mode
    bars = list(
        db.scalars(select(PriceBar).where(PriceBar.instrument_id == "^NSEI", PriceBar.source == source))
    )
    if not bars:
        return {
            "available": False,
            "reason": "Nifty 50 history is unavailable for this source. Refresh historical prices or import its CSV using instrument ID ^NSEI.",
        }
    index = pd.Series({bar.date: float(bar.close) for bar in bars}, name="benchmark")
    closes = raw.pivot(index="date", columns="id", values="close").reindex(columns=ids)
    paired = closes.join(index, how="inner").dropna().sort_index().tail(lookback + 1)
    if len(paired) < 21:
        return {"available": False, "reason": "Benchmark comparison requires at least 21 common price dates."}
    changes = paired.pct_change(fill_method=None).dropna()
    pr = changes[ids] @ weights
    br = changes["benchmark"]
    portfolio_wealth = np.r_[1, (1 + pr).cumprod().to_numpy()]
    benchmark_wealth = np.r_[1, (1 + br).cumprod().to_numpy()]
    beta = float(np.cov(pr, br, ddof=1)[0, 1] / br.var()) if br.var() > 1e-12 else None
    return {
        "available": True,
        "name": "Nifty 50",
        "basis": "Price returns excluding dividends; Yahoo closes are split-adjusted. Portfolio uses today's value weights and daily rebalancing.",
        "observations": len(pr),
        "start": str(paired.index[0]),
        "end": str(paired.index[-1]),
        "portfolio_return": float(portfolio_wealth[-1] - 1),
        "benchmark_return": float(benchmark_wealth[-1] - 1),
        "difference": float(portfolio_wealth[-1] - benchmark_wealth[-1]),
        "beta": beta,
        "tracking_error": float((pr - br).std(ddof=1) * np.sqrt(252)),
        "series": [
            {"date": str(day), "portfolio": float(p * 100), "benchmark": float(b * 100)}
            for day, p, b in zip(paired.index, portfolio_wealth, benchmark_wealth, strict=True)
        ],
    }
