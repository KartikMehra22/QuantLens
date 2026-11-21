import asyncio
import csv
import io
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .analytics.forecasting import forecast
from .analytics.risk import stress
from .bootstrap import bootstrap_database
from .config import settings
from .database import SessionLocal, engine, get_db
from .evaluations import router as evaluation_router
from .evaluations import start_jobs, stop_jobs
from .extras import router as extras_router
from .limiting import protect
from .market import replace_history, seed_catalog, seed_demo_portfolio, seed_synthetic
from .models import AnalysisRun, Holding, Instrument, Portfolio, PriceBar, User
from .recovery import router as recovery_router
from .security import DUMMY_HASH, current_session, current_user, issue_token, passwords
from .services import own_portfolio, portfolio_data
from .syncing import scheduler, sync_portfolio


@asynccontextmanager
async def lifespan(_):
    bootstrap_database()
    with SessionLocal() as db:
        seed_catalog(db)
        if settings.allow_demo:
            seed_synthetic(db)
    start_jobs()
    task = asyncio.create_task(scheduler())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        stop_jobs()


request_logger = logging.getLogger("quantlens.requests")
request_logger.setLevel(logging.INFO)
if not request_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    request_logger.addHandler(handler)
    request_logger.propagate = False

app = FastAPI(title="QuantLens API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(recovery_router)
app.include_router(evaluation_router)
app.include_router(extras_router)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    ident = uuid4().hex
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = ident
    request_logger.info(
        json.dumps(
            {
                "request_id": ident,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }
        )
    )
    return response


DB = Annotated[Session, Depends(get_db)]
Auth = Annotated[User, Depends(current_user)]


class Register(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PortfolioInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    data_mode: Literal["synthetic", "yahoo", "csv"] = "synthetic"


class HoldingInput(BaseModel):
    instrument_id: str = Field(max_length=30)
    quantity: Decimal = Field(gt=0, le=100000000, max_digits=20, decimal_places=6)
    average_cost: Decimal = Field(gt=0, le=100000000, max_digits=20, decimal_places=6)


class ScenarioInput(BaseModel):
    shock: float = Field(default=-0.1, ge=-1, le=5, allow_inf_nan=False)
    overrides: dict[str, float] = Field(default_factory=dict, max_length=100)


class CsvInput(BaseModel):
    instrument_id: str = Field(max_length=30)
    csv_text: str = Field(min_length=1, max_length=2_000_000)


def save_run(db, portfolio, kind, payload):
    run = AnalysisRun(portfolio_id=portfolio.id, kind=kind, payload=payload)
    db.add(run)
    db.commit()
    return run


def serialize_portfolio(portfolio):
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "data_mode": portfolio.data_mode,
        "auto_sync": portfolio.auto_sync,
        "last_sync_at": portfolio.last_sync_at,
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable", "service": "quantlens"})
    return {"status": "ok", "service": "quantlens", "version": "0.1.0", "database": engine.dialect.name}


@app.post("/api/v1/auth/register", status_code=201)
def register(body: Register, db: DB, request: Request):
    protect(request, "register", str(body.email), limit=10, seconds=3600)
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Name cannot be blank.")
    user = User(email=str(body.email).lower(), name=name, password_hash=passwords.hash(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from None
    return issue_token(db, user)


@app.post("/api/v1/auth/login")
def login(body: Login, db: DB, request: Request):
    protect(request, "login", str(body.email), limit=10, seconds=900)
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    valid = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    return issue_token(db, user)


@app.post("/api/v1/auth/demo")
def demo(db: DB, request: Request):
    protect(request, "demo", limit=30, seconds=3600)
    if not settings.allow_demo:
        raise HTTPException(404, "Demo mode is disabled.")
    # Each visitor gets an isolated account and portfolio; demo credentials are never shared.
    user = User(
        email=f"demo-{uuid4().hex}@quantlens.invalid",
        name="Explorer",
        password_hash=passwords.hash(uuid4().hex),
    )
    db.add(user)
    db.commit()
    seed_demo_portfolio(db, user.id)
    return issue_token(db, user)


@app.get("/api/v1/auth/me")
def me(user: Auth):
    return {"id": user.id, "name": user.name, "email": user.email}


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.patch("/api/v1/auth/me")
def update_profile(body: ProfileInput, db: DB, user: Auth):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Display name cannot be blank.")
    user.name = name
    db.commit()
    return {"id": user.id, "name": user.name, "email": user.email}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(db: DB, auth=Depends(current_session)):
    db.delete(auth[1])
    db.commit()
    return Response(status_code=204)


@app.get("/api/v1/portfolios")
def portfolios(db: DB, user: Auth):
    return [
        serialize_portfolio(p)
        for p in db.scalars(
            select(Portfolio).where(Portfolio.user_id == user.id).order_by(Portfolio.created_at)
        )
    ]


@app.post("/api/v1/portfolios", status_code=201)
def create_portfolio(body: PortfolioInput, db: DB, user: Auth):
    if not body.name.strip():
        raise HTTPException(422, "Portfolio name cannot be blank.")
    if body.data_mode == "synthetic" and not settings.allow_demo:
        raise HTTPException(422, "Synthetic mode is disabled.")
    p = Portfolio(user_id=user.id, name=body.name.strip(), data_mode=body.data_mode)
    db.add(p)
    db.commit()
    return serialize_portfolio(p)


@app.patch("/api/v1/portfolios/{portfolio_id}")
def update_portfolio(portfolio_id: str, body: PortfolioInput, db: DB, user: Auth):
    p = own_portfolio(db, user.id, portfolio_id)
    if not body.name.strip():
        raise HTTPException(422, "Portfolio name cannot be blank.")
    if body.data_mode == "synthetic" and not settings.allow_demo:
        raise HTTPException(422, "Synthetic mode is disabled.")
    p.name, p.data_mode = body.name.strip(), body.data_mode
    if body.data_mode != "yahoo":
        p.auto_sync = False
    db.flush()
    portfolio_data(db, p)
    db.commit()
    return serialize_portfolio(p)


@app.delete("/api/v1/portfolios/{portfolio_id}", status_code=204)
def delete_portfolio(portfolio_id: str, db: DB, user: Auth):
    p = own_portfolio(db, user.id, portfolio_id)
    db.delete(p)
    db.commit()
    return Response(status_code=204)


@app.get("/api/v1/instruments/search")
def search(db: DB, user: Auth, q: str = Query(default="", max_length=80)):
    # Escape SQL wildcard characters so search remains a literal substring match.
    term = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{term}%"
    rows = db.scalars(
        select(Instrument)
        .where(
            Instrument.exchange != "INDEX",
            or_(Instrument.name.ilike(pattern, escape="\\"), Instrument.symbol.ilike(pattern, escape="\\")),
        )
        .order_by(Instrument.symbol, Instrument.exchange)
        .limit(30)
    )
    return [
        {
            "id": i.id,
            "symbol": i.symbol,
            "name": i.name,
            "exchange": i.exchange,
            "sector": i.sector,
            "color": i.color,
        }
        for i in rows
    ]


@app.get("/api/v1/instruments/{instrument_id}/prices")
def instrument_prices(
    instrument_id: str,
    db: DB,
    user: Auth,
    source: Literal["synthetic", "yahoo", "csv"] = "synthetic",
    portfolio_id: str | None = None,
):
    if not db.get(Instrument, instrument_id):
        raise HTTPException(404, "Instrument not found.")
    source_key = source
    if source == "csv":
        if not portfolio_id:
            raise HTTPException(422, "A portfolio ID is required for private CSV prices.")
        own_portfolio(db, user.id, portfolio_id)
        source_key = f"csv:{portfolio_id}"
    bars = list(
        db.scalars(
            select(PriceBar)
            .where(PriceBar.instrument_id == instrument_id, PriceBar.source == source_key)
            .order_by(PriceBar.date.desc())
            .limit(252)
        )
    )
    return {
        "source": source,
        "prices": [
            {
                "date": str(b.date),
                "close": float(b.close),
                "adjusted_close": float(b.adjusted_close),
                "open": float(b.open) if b.open is not None else None,
                "high": float(b.high) if b.high is not None else None,
                "low": float(b.low) if b.low is not None else None,
                "volume": int(b.volume) if b.volume is not None else None,
            }
            for b in reversed(bars)
        ],
    }


@app.get("/api/v1/portfolios/{portfolio_id}/holdings")
def list_holdings(portfolio_id: str, db: DB, user: Auth):
    own_portfolio(db, user.id, portfolio_id)
    return [
        {
            "id": h.id,
            "instrument_id": i.id,
            "quantity": float(h.quantity),
            "average_cost": float(h.average_cost),
            "symbol": i.symbol,
            "name": i.name,
            "exchange": i.exchange,
            "sector": i.sector,
            "color": i.color,
        }
        for h, i in db.execute(
            select(Holding, Instrument).join(Instrument).where(Holding.portfolio_id == portfolio_id)
        )
    ]


@app.post("/api/v1/portfolios/{portfolio_id}/holdings", status_code=201)
def add_holding(portfolio_id: str, body: HoldingInput, db: DB, user: Auth):
    own_portfolio(db, user.id, portfolio_id)
    instrument = db.get(Instrument, body.instrument_id)
    if not instrument or instrument.exchange == "INDEX":
        raise HTTPException(422, "Select a supported equity instrument.")
    holding = Holding(portfolio_id=portfolio_id, **body.model_dump())
    db.add(holding)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This instrument is already held. Edit its quantity and average cost."
        ) from None
    return {"id": holding.id}


@app.patch("/api/v1/portfolios/{portfolio_id}/holdings/{holding_id}")
def edit_holding(portfolio_id: str, holding_id: str, body: HoldingInput, db: DB, user: Auth):
    own_portfolio(db, user.id, portfolio_id)
    h = db.get(Holding, holding_id)
    if not h or h.portfolio_id != portfolio_id:
        raise HTTPException(404, "Holding not found.")
    if h.instrument_id != body.instrument_id:
        raise HTTPException(422, "An existing holding's instrument cannot be changed.")
    h.quantity, h.average_cost = body.quantity, body.average_cost
    db.commit()
    return {"id": h.id}


@app.delete("/api/v1/portfolios/{portfolio_id}/holdings/{holding_id}", status_code=204)
def remove_holding(portfolio_id: str, holding_id: str, db: DB, user: Auth):
    own_portfolio(db, user.id, portfolio_id)
    h = db.get(Holding, holding_id)
    if not h or h.portfolio_id != portfolio_id:
        raise HTTPException(404, "Holding not found.")
    db.delete(h)
    db.commit()
    return Response(status_code=204)


@app.get("/api/v1/portfolios/{portfolio_id}/summary")
def summary(portfolio_id: str, db: DB, user: Auth, lookback: int = Query(252, ge=21, le=1260)):
    return portfolio_data(db, own_portfolio(db, user.id, portfolio_id), lookback)[0]


@app.post("/api/v1/portfolios/{portfolio_id}/analyses", status_code=201)
def save_analysis(portfolio_id: str, db: DB, user: Auth):
    p = own_portfolio(db, user.id, portfolio_id)
    data, _ = portfolio_data(db, p)
    if not data["holdings"]:
        raise HTTPException(422, "Add holdings before saving an analysis.")
    run = save_run(db, p, "risk", data)
    return {"id": run.id, "created_at": run.created_at, "kind": run.kind}


@app.post("/api/v1/portfolios/{portfolio_id}/stress-tests")
def scenario(portfolio_id: str, body: ScenarioInput, db: DB, user: Auth):
    p = own_portfolio(db, user.id, portfolio_id)
    data, _ = portfolio_data(db, p)
    holdings = data["holdings"]
    if not holdings:
        raise HTTPException(422, "Add holdings before running a scenario.")
    if set(body.overrides) - {h["instrument_id"] for h in holdings}:
        raise HTTPException(422, "Scenario overrides must refer to holdings in this portfolio.")
    shocks = [body.overrides.get(h["instrument_id"], body.shock) for h in holdings]
    try:
        result = stress([h["value"] for h in holdings], shocks)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    result.update(
        {
            "as_of": data["as_of"],
            "data_mode": p.data_mode,
            "shock": body.shock,
            "holdings": [
                {**h, "shock": s, "change": c}
                for h, s, c in zip(holdings, shocks, result["holding_changes"], strict=True)
            ],
        }
    )
    run = save_run(db, p, "stress", result)
    return {**result, "run_id": run.id}


@app.post("/api/v1/portfolios/{portfolio_id}/forecasts")
def volatility_forecast(
    portfolio_id: str,
    db: DB,
    user: Auth,
    horizon: int = Query(5, ge=1, le=20),
    lookback: int = Query(756, ge=252, le=1260),
):
    p = own_portfolio(db, user.id, portfolio_id)
    data, returns = portfolio_data(db, p, lookback)
    if returns is None:
        raise HTTPException(422, "Add holdings before generating forecasts.")
    try:
        result = forecast(returns.to_numpy(), horizon)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    result.update(
        {
            "as_of": data["as_of"],
            "data_mode": p.data_mode,
            "holdings": data["holdings"],
            "assumption": data["methodology"],
        }
    )
    run = save_run(db, p, "forecast", result)
    return {**result, "run_id": run.id}


@app.post("/api/v1/portfolios/{portfolio_id}/data-refreshes")
def refresh_prices(portfolio_id: str, db: DB, user: Auth):
    p = own_portfolio(db, user.id, portfolio_id)
    if not db.scalar(select(Holding.id).where(Holding.portfolio_id == p.id)):
        raise HTTPException(422, "Add at least one holding before refreshing.")
    try:
        return sync_portfolio(db, p)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            502,
            "Market data provider is unavailable or returned invalid history. Existing data is unchanged; retry later or import CSV.",
        ) from None


@app.post("/api/v1/portfolios/{portfolio_id}/prices/import")
def import_prices(portfolio_id: str, body: CsvInput, db: DB, user: Auth):
    p = own_portfolio(db, user.id, portfolio_id)
    if body.instrument_id != "^NSEI" and not db.scalar(
        select(Holding.id).where(Holding.portfolio_id == p.id, Holding.instrument_id == body.instrument_id)
    ):
        raise HTTPException(422, "Import prices for an instrument held in this portfolio.")
    try:
        frame = pd.read_csv(io.StringIO(body.csv_text), dtype={"date": str})
        if not {"date", "close", "adjusted_close"}.issubset(frame.columns):
            raise ValueError("Required columns: date,close,adjusted_close.")
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise").dt.date
        frame = frame.set_index("date")[["close", "adjusted_close"]].astype(float)
        if len(frame) < 2 or len(frame) > 10000 or frame.index.duplicated().any():
            raise ValueError("Supply 2–10,000 unique daily records.")
        if (
            frame.index.max() >= date.today()
            or (frame < 0.000001).any().any()
            or (frame > 1e12).any().any()
            or not np.isfinite(frame.to_numpy()).all()
        ):
            raise ValueError("Use finite positive prices on completed historical dates.")
        replace_history(
            db,
            body.instrument_id,
            frame.rename(columns={"close": "Close", "adjusted_close": "Adj Close"}),
            f"csv:{p.id}",
        )
        db.commit()
    except (ValueError, KeyError, TypeError) as exc:
        db.rollback()
        raise HTTPException(422, f"Invalid CSV: {exc}") from None
    return {
        "rows": len(frame),
        "source": "csv",
        "message": "Imported. Switch portfolio source to CSV after importing all holdings.",
    }


@app.get("/api/v1/portfolios/{portfolio_id}/reports")
def reports(portfolio_id: str, db: DB, user: Auth):
    own_portfolio(db, user.id, portfolio_id)
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "created_at": r.created_at,
            "as_of": r.payload.get("as_of"),
            "data_mode": r.payload.get("data_mode"),
        }
        for r in db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.portfolio_id == portfolio_id)
            .order_by(AnalysisRun.created_at.desc())
            .limit(50)
        )
    ]


@app.get("/api/v1/portfolios/{portfolio_id}/reports/{run_id}")
def report_detail(portfolio_id: str, run_id: str, db: DB, user: Auth):
    own_portfolio(db, user.id, portfolio_id)
    run = db.get(AnalysisRun, run_id)
    if not run or run.portfolio_id != portfolio_id:
        raise HTTPException(404, "Report not found.")
    return {"id": run.id, "kind": run.kind, "created_at": run.created_at, "payload": run.payload}


@app.get("/api/v1/portfolios/{portfolio_id}/export.csv")
def export_csv(portfolio_id: str, db: DB, user: Auth):
    data, _ = portfolio_data(db, own_portfolio(db, user.id, portfolio_id))
    output = io.StringIO()
    fields = ["symbol", "exchange", "quantity", "average_cost", "price", "value", "invested", "pnl", "weight"]
    writer = csv.DictWriter(output, fieldnames=[*fields, "as_of", "data_mode"], extrasaction="ignore")
    writer.writeheader()
    for holding in data["holdings"]:
        writer.writerow({**holding, "as_of": data["as_of"], "data_mode": data["data_mode"]})
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="quantlens-holdings.csv"'},
    )


@app.get("/api/v1/portfolios/{portfolio_id}/export.pdf")
def export_pdf(portfolio_id: str, db: DB, user: Auth):
    from .models import ForecastEvaluation
    from .reporting import portfolio_pdf

    data, _ = portfolio_data(db, own_portfolio(db, user.id, portfolio_id))
    latest = db.scalar(
        select(ForecastEvaluation)
        .where(ForecastEvaluation.portfolio_id == portfolio_id, ForecastEvaluation.status == "completed")
        .order_by(ForecastEvaluation.created_at.desc())
        .limit(1)
    )
    return Response(
        portfolio_pdf(data, latest),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="quantlens-risk-report.pdf"'},
    )
