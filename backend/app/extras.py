from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from .database import SessionLocal
from .models import DataSyncRun
from .security import current_user
from .services import own_portfolio, portfolio_data

router = APIRouter(prefix="/api/v1", tags=["Portfolio comparison and sync settings"])


class SyncSettings(BaseModel):
    auto_sync: bool


@router.patch("/portfolios/{portfolio_id}/settings")
def sync_settings(portfolio_id: str, body: SyncSettings, user=Depends(current_user)):
    with SessionLocal() as db:
        portfolio = own_portfolio(db, user.id, portfolio_id)
        if body.auto_sync and portfolio.data_mode != "yahoo":
            raise HTTPException(422, "Download historical market data before enabling automatic refresh.")
        portfolio.auto_sync = body.auto_sync
        db.commit()
        return {"auto_sync": portfolio.auto_sync, "last_sync_at": portfolio.last_sync_at}


@router.get("/portfolios/{portfolio_id}/sync-history")
def sync_history(portfolio_id: str, user=Depends(current_user)):
    with SessionLocal() as db:
        own_portfolio(db, user.id, portfolio_id)
        return [
            {
                "id": run.id,
                "status": run.status,
                "created_at": run.created_at,
                "instruments": run.instruments,
                "message": run.message,
            }
            for run in db.scalars(
                select(DataSyncRun)
                .where(DataSyncRun.portfolio_id == portfolio_id)
                .order_by(DataSyncRun.created_at.desc())
                .limit(20)
            )
        ]


@router.get("/portfolio-comparison")
def compare_portfolios(ids: list[str] = Query(min_length=2, max_length=5), user=Depends(current_user)):
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Select distinct portfolios.")
    result = []
    with SessionLocal() as db:
        for ident in ids:
            portfolio = own_portfolio(db, user.id, ident)
            data, _ = portfolio_data(db, portfolio)
            result.append(
                {
                    key: data.get(key)
                    for key in [
                        "portfolio_id",
                        "name",
                        "data_mode",
                        "as_of",
                        "value",
                        "invested",
                        "pnl_pct",
                        "metrics",
                        "period_start",
                        "period_end",
                    ]
                }
            )
    return {
        "portfolios": result,
        "assumption": "Each portfolio uses its own available period and current weights. Check source and dates before comparing risk estimates.",
    }
