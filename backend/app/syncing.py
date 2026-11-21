import asyncio
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock

from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .market import fetch_yahoo, replace_history
from .models import DataSyncRun, Holding, Portfolio
from .security import utc
from .services import portfolio_data

sync_lock = Lock()
logger = logging.getLogger("quantlens.sync")


def sync_portfolio(db, portfolio):
    ids = list(db.scalars(select(Holding.instrument_id).where(Holding.portfolio_id == portfolio.id)))
    if not ids:
        raise ValueError("Add at least one holding before refreshing.")
    benchmark_ok = True
    with sync_lock:
        histories = {ident: fetch_yahoo(ident) for ident in ids}
        try:
            benchmark = fetch_yahoo("^NSEI")
        except Exception:
            benchmark = None
            benchmark_ok = False
        for ident, frame in histories.items():
            replace_history(db, ident, frame, "yahoo")
        if benchmark is not None:
            replace_history(db, "^NSEI", benchmark, "yahoo")
        portfolio.data_mode = "yahoo"
        portfolio.last_sync_at = datetime.now(timezone.utc)
        db.flush()
        portfolio_data(db, portfolio)
        run = DataSyncRun(
            portfolio_id=portfolio.id,
            status="completed",
            instruments=len(ids),
            message="Historical prices updated."
            if benchmark_ok
            else "Holdings updated; benchmark download unavailable.",
        )
        db.add(run)
        db.commit()
    return {
        "status": "updated",
        "instruments": len(ids),
        "source": "yahoo",
        "benchmark_updated": benchmark_ok,
    }


def sync_due():
    with SessionLocal() as db:
        due = [
            p.id
            for p in db.scalars(
                select(Portfolio).where(Portfolio.auto_sync.is_(True), Portfolio.data_mode == "yahoo")
            )
            if p.last_sync_at is None
            or utc(p.last_sync_at) <= datetime.now(timezone.utc) - timedelta(hours=24)
        ]
    for ident in due:
        with SessionLocal() as db:
            portfolio = db.get(Portfolio, ident)
            if not portfolio:
                continue
            try:
                sync_portfolio(db, portfolio)
            except Exception:
                db.rollback()
                db.add(
                    DataSyncRun(
                        portfolio_id=ident,
                        status="failed",
                        message="Provider unavailable or history validation failed.",
                    )
                )
                # Delay another automatic attempt for a day; manual refresh remains available.
                portfolio = db.get(Portfolio, ident)
                if portfolio:
                    portfolio.last_sync_at = datetime.now(timezone.utc)
                db.commit()
                logger.warning("Scheduled historical refresh failed", extra={"portfolio_id": ident})


async def scheduler():
    while True:
        await asyncio.sleep(max(10, settings.sync_poll_seconds))
        await asyncio.to_thread(sync_due)
