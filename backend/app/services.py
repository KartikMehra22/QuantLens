import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analytics.risk import diversification, metrics
from .benchmark import compare_benchmark
from .models import Holding, Instrument, Portfolio, PriceBar


def own_portfolio(db: Session, user_id: str, portfolio_id: str):
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None or portfolio.user_id != user_id:
        raise HTTPException(404, "Portfolio not found.")
    return portfolio


def portfolio_data(db: Session, portfolio: Portfolio, lookback=252):
    rows = list(
        db.execute(
            select(Holding, Instrument)
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .where(Holding.portfolio_id == portfolio.id)
            .order_by(Instrument.symbol)
        )
    )
    if not rows:
        return {
            "portfolio_id": portfolio.id,
            "name": portfolio.name,
            "data_mode": portfolio.data_mode,
            "as_of": None,
            "holdings": [],
            "invested": 0,
            "value": 0,
            "pnl": 0,
            "pnl_pct": 0,
            "series": [],
            "metrics": None,
            "diversification": None,
            "warnings": [],
            "methodology": "Fixed-weight daily-rebalanced hypothetical historical portfolio.",
        }, None
    ids = [i.id for _, i in rows]
    source_key = f"csv:{portfolio.id}" if portfolio.data_mode == "csv" else portfolio.data_mode
    bars = list(
        db.scalars(select(PriceBar).where(PriceBar.instrument_id.in_(ids), PriceBar.source == source_key))
    )
    present = {b.instrument_id for b in bars}
    missing = set(ids) - present
    if missing:
        raise HTTPException(
            409,
            "Prices unavailable for " + ", ".join(sorted(missing)) + ". Refresh market data or import CSV.",
        )
    raw = pd.DataFrame(
        [
            {
                "date": b.date,
                "id": b.instrument_id,
                "close": float(b.close),
                "adjusted": float(b.adjusted_close),
            }
            for b in bars
        ]
    )
    prices = raw.pivot(index="date", columns="id", values="adjusted").reindex(columns=ids).sort_index()
    before = len(prices)
    prices = prices.dropna()
    if len(prices) < 2:
        raise HTTPException(409, "At least two common price dates are required across all holdings.")
    as_of = prices.index[-1]
    closes = raw.loc[raw.date == as_of].set_index("id")["close"]
    holding_values = np.array([float(h.quantity) * closes[i.id] for h, i in rows])
    value = float(holding_values.sum())
    weights = holding_values / value
    holdings = []
    for index, (h, i) in enumerate(rows):
        invested = float(h.quantity * h.average_cost)
        holdings.append(
            {
                "id": h.id,
                "instrument_id": i.id,
                "symbol": i.symbol,
                "name": i.name,
                "exchange": i.exchange,
                "sector": i.sector,
                "color": i.color,
                "quantity": float(h.quantity),
                "average_cost": float(h.average_cost),
                "price": float(closes[i.id]),
                "value": float(holding_values[index]),
                "invested": invested,
                "pnl": float(holding_values[index] - invested),
                "pnl_pct": float(holding_values[index] / invested - 1),
                "weight": float(weights[index]),
            }
        )
    returns = prices.pct_change(fill_method=None).dropna().tail(lookback)
    portfolio_returns = returns @ weights
    wealth = np.r_[1.0, (1 + portfolio_returns).cumprod().to_numpy()]
    dates = [prices.index[-len(returns) - 1], *returns.index]
    invested = sum(h["invested"] for h in holdings)
    div = diversification(returns, weights) if len(returns) >= 20 else None
    if div:
        div["symbols"] = [h["symbol"] for h in holdings]
        for h, contribution in zip(holdings, div["contributions"], strict=True):
            h["risk_contribution"] = contribution["percentage"]
    warnings = []
    if portfolio.data_mode == "synthetic":
        warnings.append("Synthetic demonstration prices. Not actual NSE/BSE observations.")
    if before != len(prices):
        warnings.append(
            f"Excluded {before - len(prices)} dates with incomplete cross-asset prices; no forward filling."
        )
    if len(returns) < 252:
        warnings.append("Less than one trading year of observations; tail-risk estimates may be unstable.")
    warnings.append(
        "Historical simulation uses today's value weights and daily rebalancing; it is not your actual investment history."
    )
    result = {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "data_mode": portfolio.data_mode,
        "as_of": str(as_of),
        "holdings": holdings,
        "invested": invested,
        "value": value,
        "pnl": value - invested,
        "pnl_pct": value / invested - 1 if invested else 0,
        "series": [{"date": str(day), "value": float(v * 100)} for day, v in zip(dates, wealth, strict=True)],
        "metrics": metrics(portfolio_returns),
        "diversification": div,
        "warnings": warnings,
        "period_start": str(dates[0]),
        "period_end": str(as_of),
        "methodology": "Fixed-weight daily-rebalanced hypothetical historical portfolio; adjusted close returns; current value weights; 252-day annualization; one-day 95% historical VaR/CVaR; 6% effective annual risk-free assumption.",
    }
    result["benchmark"] = compare_benchmark(db, portfolio, ids, weights, raw, lookback)
    return result, portfolio_returns
