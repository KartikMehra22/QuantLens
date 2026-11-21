"""Provider boundary: synthetic demo data and Yahoo prices never share a source key."""

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Holding, Instrument, Portfolio, PriceBar

CATALOG = [
    ("RELIANCE.NS", "RELIANCE", "Reliance Industries", "NSE", "Energy", "#A6E8B5", 2800),
    ("TCS.NS", "TCS", "Tata Consultancy Services", "NSE", "Technology", "#A8B8FF", 3900),
    ("HDFCBANK.NS", "HDFCBANK", "HDFC Bank", "NSE", "Financials", "#F5CB8B", 1650),
    ("INFY.NS", "INFY", "Infosys", "NSE", "Technology", "#B8A5E8", 1500),
    ("ICICIBANK.NS", "ICICIBANK", "ICICI Bank", "NSE", "Financials", "#86C9DF", 1100),
    ("ITC.NS", "ITC", "ITC Limited", "NSE", "Consumer Staples", "#EDA7B2", 430),
    ("BHARTIARTL.NS", "BHARTIARTL", "Bharti Airtel", "NSE", "Communication", "#F7AE7D", 1450),
    ("LT.NS", "LT", "Larsen & Toubro", "NSE", "Industrials", "#91CDC0", 3500),
    ("SUNPHARMA.NS", "SUNPHARMA", "Sun Pharmaceutical", "NSE", "Healthcare", "#D5B3D7", 1600),
    ("TATAMOTORS.NS", "TATAMOTORS", "Tata Motors", "NSE", "Consumer Discretionary", "#C5CB83", 900),
    ("RELIANCE.BO", "RELIANCE", "Reliance Industries", "BSE", "Energy", "#A6E8B5", 2800),
    ("TCS.BO", "TCS", "Tata Consultancy Services", "BSE", "Technology", "#A8B8FF", 3900),
    ("^NSEI", "NIFTY50", "Nifty 50", "INDEX", "Index", "#6B7891", 22000),
]


def seed_catalog(db: Session):
    for ident, symbol, name, exchange, sector, color, _ in CATALOG:
        if db.get(Instrument, ident) is None:
            db.add(
                Instrument(id=ident, symbol=symbol, name=name, exchange=exchange, sector=sector, color=color)
            )
    db.commit()


def seed_synthetic(db: Session):
    if db.scalar(select(PriceBar.id).where(PriceBar.source == "synthetic").limit(1)):
        return
    rng = np.random.default_rng(20261120)
    days = pd.bdate_range(end=date.today() - timedelta(days=1), periods=800)
    # Correlated, heteroskedastic synthetic returns, not observed market prices.
    market = rng.normal(0.00035, 0.009, len(days))
    market[300:330] *= 2.8
    sectors = {sector: rng.normal(0, 0.005, len(days)) for *_, sector, color, base in CATALOG}
    for index, (ident, _, _, _, sector, _, base) in enumerate(CATALOG):
        returns = (
            market
            if ident == "^NSEI"
            else (0.8 + index * 0.025) * market + sectors[sector] + rng.normal(0.00012, 0.008, len(days))
        )
        prices = base * np.cumprod(1 + returns)
        db.add_all(
            [
                PriceBar(
                    instrument_id=ident,
                    date=day.date(),
                    close=Decimal(str(round(price, 6))),
                    adjusted_close=Decimal(str(round(price, 6))),
                    source="synthetic",
                )
                for day, price in zip(days, prices, strict=True)
            ]
        )
    db.commit()


def seed_demo_portfolio(db: Session, user_id: str):
    portfolio = Portfolio(user_id=user_id, name="Long-term equity", data_mode="synthetic")
    db.add(portfolio)
    db.flush()
    for ident, quantity, cost_factor in [
        ("RELIANCE.NS", 40, 0.86),
        ("TCS.NS", 20, 0.91),
        ("HDFCBANK.NS", 65, 0.94),
        ("INFY.NS", 35, 1.04),
        ("ICICIBANK.NS", 45, 0.89),
        ("ITC.NS", 100, 0.95),
    ]:
        price = db.scalar(
            select(PriceBar)
            .where(PriceBar.instrument_id == ident, PriceBar.source == "synthetic")
            .order_by(PriceBar.date.desc())
            .limit(1)
        )
        db.add(
            Holding(
                portfolio_id=portfolio.id,
                instrument_id=ident,
                quantity=quantity,
                average_cost=round(float(price.close) * cost_factor, 2),
            )
        )
    db.commit()
    return portfolio


def fetch_yahoo(instrument_id: str) -> pd.DataFrame:
    import yfinance as yf

    frame = yf.Ticker(instrument_id).history(period="5y", auto_adjust=False, timeout=15)
    if frame.empty or "Adj Close" not in frame or "Close" not in frame:
        raise ValueError(f"No usable adjusted history returned for {instrument_id}.")
    frame = frame[[c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in frame]].copy()
    frame.index = pd.Index([v.date() for v in frame.index])
    frame = frame.loc[frame.index < date.today()]
    if (
        frame.empty
        or frame.isna().any().any()
        or not np.isfinite(frame.to_numpy()).all()
        or (frame[["Close", "Adj Close"]] < 0.000001).any().any()
        or (frame[["Close", "Adj Close"]] > 1e12).any().any()
        or (frame < 0).any().any()
    ):
        raise ValueError(f"Invalid historical prices for {instrument_id}.")
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def replace_history(db: Session, ident: str, frame: pd.DataFrame, source: str):
    from sqlalchemy import delete

    db.execute(delete(PriceBar).where(PriceBar.instrument_id == ident, PriceBar.source == source))
    db.add_all(
        [
            PriceBar(
                instrument_id=ident,
                date=day,
                close=Decimal(str(float(row["Close"]))),
                adjusted_close=Decimal(str(float(row["Adj Close"]))),
                source=source,
                open=Decimal(str(float(row["Open"]))) if "Open" in row else None,
                high=Decimal(str(float(row["High"]))) if "High" in row else None,
                low=Decimal(str(float(row["Low"]))) if "Low" in row else None,
                volume=int(row["Volume"]) if "Volume" in row else None,
            )
            for day, row in frame.iterrows()
        ]
    )
