import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event, Lock

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from .analytics.forecasting import evaluate
from .database import SessionLocal
from .models import ForecastEvaluation, Portfolio
from .security import current_user
from .services import own_portfolio, portfolio_data

router = APIRouter(prefix="/api/v1", tags=["Forecast evaluation"])
executor = None
stopped = Event()
enqueue_lock = Lock()


class EvaluationInput(BaseModel):
    training_window: int = Field(default=504, ge=252, le=1000)
    test_days: int = Field(default=60, ge=5, le=252)


class Cancelled(Exception):
    pass


def start_jobs():
    global executor
    stopped.clear()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quantlens-evaluation")
    with SessionLocal() as db:
        db.execute(
            update(ForecastEvaluation)
            .where(ForecastEvaluation.status.in_(["queued", "running"]))
            .values(status="failed", error="Server restarted before evaluation completed. Run it again.")
        )
        db.commit()


def stop_jobs():
    global executor
    stopped.set()
    if executor:
        executor.shutdown(wait=True, cancel_futures=True)
        executor = None


def run_evaluation(ident):
    with SessionLocal() as db:
        job = db.get(ForecastEvaluation, ident)
        if not job or job.status == "cancelled":
            return
        inputs = dict(job.payload)
        job.status = "running"
        db.commit()

    def progress(done, total):
        if stopped.is_set():
            raise Cancelled()
        with SessionLocal() as db:
            job = db.get(ForecastEvaluation, ident)
            if not job or job.status == "cancelled":
                raise Cancelled()
            job.progress = done
            db.commit()

    try:
        result = evaluate(
            inputs["return_values"], inputs["training_window"], inputs["test_days"], on_progress=progress
        )
        with SessionLocal() as db:
            job = db.get(ForecastEvaluation, ident)
            if job and job.status != "cancelled":
                job.payload = {**inputs, **result, "finished_at": datetime.now(timezone.utc).isoformat()}
                job.status, job.progress = "completed", job.total
                db.commit()
    except Cancelled:
        with SessionLocal() as db:
            job = db.get(ForecastEvaluation, ident)
            if job:
                job.status = "cancelled"
                db.commit()
    except Exception:
        logging.getLogger("quantlens.evaluation").exception(
            "Evaluation failed", extra={"evaluation_id": ident}
        )
        with SessionLocal() as db:
            job = db.get(ForecastEvaluation, ident)
            if job:
                job.status, job.error = (
                    "failed",
                    "A model could not converge or the evaluation data was unsuitable. Try a different period.",
                )
                db.commit()


def serialize(job, detail=False):
    result = {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "total": job.total,
        "created_at": job.created_at,
        "error": job.error,
        "data_mode": job.payload["data_mode"],
        "as_of": job.payload["as_of"],
        "training_window": job.payload["training_window"],
        "test_days": job.payload["test_days"],
    }
    if detail:
        result["result"] = job.payload if job.status == "completed" else None
    return result


@router.post("/portfolios/{portfolio_id}/evaluations", status_code=202)
def create_evaluation(portfolio_id: str, body: EvaluationInput, user=Depends(current_user)):
    with enqueue_lock, SessionLocal() as db:
        if executor is None:
            raise HTTPException(503, "Evaluation worker is unavailable.")
        portfolio = own_portfolio(db, user.id, portfolio_id)
        active = ["queued", "running"]
        if db.scalar(
            select(ForecastEvaluation.id)
            .join(Portfolio)
            .where(Portfolio.user_id == user.id, ForecastEvaluation.status.in_(active))
            .limit(1)
        ):
            raise HTTPException(409, "An evaluation is already running for your account.")
        if (
            db.scalar(
                select(func.count())
                .select_from(ForecastEvaluation)
                .where(ForecastEvaluation.status.in_(active))
            )
            >= 8
        ):
            raise HTTPException(429, "The evaluation queue is full. Retry later.")
        data, returns = portfolio_data(db, portfolio, body.training_window + body.test_days)
        if returns is None or len(returns) < body.training_window + body.test_days:
            raise HTTPException(
                422, "Not enough aligned daily returns for this training and evaluation period."
            )
        payload = {
            **body.model_dump(),
            "data_mode": portfolio.data_mode,
            "as_of": data["as_of"],
            "holdings": data["holdings"],
            "methodology": data["methodology"],
            "return_dates": [str(d) for d in returns.index],
            "return_values": returns.tolist(),
            "evaluation_dates": [str(d) for d in returns.index[-body.test_days :]],
            "limitation": "Squared daily returns are a noisy variance proxy. Current holdings and weights are selected retrospectively. Synthetic data validates software only.",
        }
        job = ForecastEvaluation(portfolio_id=portfolio.id, total=body.test_days, payload=payload)
        db.add(job)
        db.commit()
        executor.submit(run_evaluation, job.id)
        return serialize(job)


@router.get("/portfolios/{portfolio_id}/evaluations")
def list_evaluations(portfolio_id: str, user=Depends(current_user)):
    with SessionLocal() as db:
        own_portfolio(db, user.id, portfolio_id)
        jobs = db.scalars(
            select(ForecastEvaluation)
            .where(ForecastEvaluation.portfolio_id == portfolio_id)
            .order_by(ForecastEvaluation.created_at.desc())
            .limit(20)
        )
        return [serialize(job) for job in jobs]


def owned_job(db, user, portfolio_id, ident):
    own_portfolio(db, user.id, portfolio_id)
    job = db.get(ForecastEvaluation, ident)
    if not job or job.portfolio_id != portfolio_id:
        raise HTTPException(404, "Evaluation not found.")
    return job


@router.get("/portfolios/{portfolio_id}/evaluations/{ident}")
def evaluation_detail(portfolio_id: str, ident: str, user=Depends(current_user)):
    with SessionLocal() as db:
        return serialize(owned_job(db, user, portfolio_id, ident), True)


@router.delete("/portfolios/{portfolio_id}/evaluations/{ident}")
def cancel_evaluation(portfolio_id: str, ident: str, user=Depends(current_user)):
    with SessionLocal() as db:
        job = owned_job(db, user, portfolio_id, ident)
        if job.status in ["queued", "running"]:
            job.status = "cancelled"
            db.commit()
        return serialize(job)


@router.get("/portfolios/{portfolio_id}/evaluations/{ident}/export.json")
def export_evaluation(portfolio_id: str, ident: str, user=Depends(current_user)):
    import json

    with SessionLocal() as db:
        job = owned_job(db, user, portfolio_id, ident)
        if job.status != "completed":
            raise HTTPException(409, "Evaluation has not completed.")
        return Response(
            json.dumps(job.payload, indent=2, allow_nan=False),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="quantlens-evaluation.json"'},
        )
