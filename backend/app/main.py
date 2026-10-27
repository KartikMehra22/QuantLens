import csv
import io
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .analytics.forecasting import forecast
from .analytics.risk import stress
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .market import fetch_yahoo, replace_history, seed_catalog, seed_demo_portfolio, seed_synthetic
from .models import AnalysisRun, Holding, Instrument, Portfolio, PriceBar, User
from .security import DUMMY_HASH, current_session, current_user, issue_token, passwords
from .services import own_portfolio, portfolio_data


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_catalog(db)
        if settings.allow_demo:
            seed_synthetic(db)
    yield


app = FastAPI(title="QuantLens API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
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
    return {"id": portfolio.id, "name": portfolio.name, "data_mode": portfolio.data_mode}


@app.get("/health")
def health():
    return {"status": "ok", "service": "quantlens", "version": "0.1.0"}


@app.post("/api/v1/auth/register", status_code=201)
def register(body: Register, db: DB):
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
def login(body: Login, db: DB):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    valid = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    return issue_token(db, user)


@app.post("/api/v1/auth/demo")
def demo(db: DB):
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
            {"date": str(b.date), "close": float(b.close), "adjusted_close": float(b.adjusted_close)}
            for b in reversed(bars)
        ],
    }


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
    ids = list(db.scalars(select(Holding.instrument_id).where(Holding.portfolio_id == p.id)))
    if not ids:
        raise HTTPException(422, "Add at least one holding before refreshing.")
    try:
        # Retrieve all histories first; failures never switch the portfolio to partially downloaded data.
        histories = {ident: fetch_yahoo(ident) for ident in ids}
        for ident, frame in histories.items():
            replace_history(db, ident, frame, "yahoo")
        p.data_mode = "yahoo"
        db.flush()
        portfolio_data(db, p)  # Validate cross-asset overlap before committing source switch.
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            502,
            "Market data provider is unavailable or returned invalid history. Existing data is unchanged; retry later or import CSV.",
        ) from None
    return {"status": "updated", "instruments": len(ids), "source": "yahoo"}


@app.post("/api/v1/portfolios/{portfolio_id}/prices/import")
def import_prices(portfolio_id: str, body: CsvInput, db: DB, user: Auth):
    p = own_portfolio(db, user.id, portfolio_id)
    if not db.scalar(
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
            or (frame <= 0).any().any()
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
    from html import escape

    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    data, _ = portfolio_data(db, own_portfolio(db, user.id, portfolio_id))
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph("QuantLens | Portfolio risk report", styles["Title"]),
        Paragraph(escape(data["name"]), styles["Heading2"]),
        Paragraph(
            f"Price date: {data['as_of']} | Source: {data['data_mode']} | Generated: {datetime.now(timezone.utc).date()}",
            styles["Normal"],
        ),
        Spacer(1, 14),
        Paragraph(
            f"Portfolio value: INR {data['value']:,.2f} | Unrealized P&amp;L: INR {data['pnl']:,.2f}",
            styles["Normal"],
        ),
    ]
    table = [["Instrument", "Quantity", "Close (INR)", "Value (INR)", "Weight"]]
    table += [
        [h["symbol"], str(h["quantity"]), f"{h['price']:,.2f}", f"{h['value']:,.2f}", f"{h['weight']:.1%}"]
        for h in data["holdings"]
    ]
    t = Table(table, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173B32")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ]
        )
    )
    story += [Spacer(1, 15), t, Spacer(1, 15)]
    if data["metrics"]:
        for key, value in data["metrics"].items():
            story.append(
                Paragraph(
                    f"{key.replace('_', ' ').title()}: {value:.6f}"
                    if value is not None
                    else f"{key}: unavailable",
                    styles["Normal"],
                )
            )
    story += [
        Spacer(1, 14),
        Paragraph("Methodology and limitations", styles["Heading2"]),
        Paragraph(escape(data["methodology"]), styles["Normal"]),
    ]
    for warning in data["warnings"]:
        story += [Spacer(1, 7), Paragraph(escape(warning), styles["Normal"])]
    story.append(
        Paragraph(
            "Educational analysis. Historical estimates do not guarantee future outcomes.", styles["Normal"]
        )
    )
    SimpleDocTemplate(output, title="QuantLens risk report").build(story)
    return Response(
        output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="quantlens-risk-report.pdf"'},
    )
