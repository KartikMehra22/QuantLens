import hmac
import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select, update

from .config import settings
from .database import SessionLocal
from .limiting import protect
from .models import AuthSession, PasswordReset, User
from .security import passwords, rotate_token, utc

router = APIRouter(prefix="/api/v1/auth", tags=["Account recovery and renewal"])


class RefreshInput(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirm(ResetRequest):
    code: str = Field(pattern=r"^\d{8}$")
    password: str = Field(min_length=8, max_length=128)


def code_hash(email, code):
    return hmac.new(settings.jwt_secret.encode(), f"reset:{email}:{code}".encode(), "sha256").hexdigest()


def deliver(email, code):
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = email
    message["Subject"] = "Your QuantLens password reset code"
    message.set_content(
        f"Your reset code is {code}.\nIt expires in {settings.reset_minutes} minutes.\nIf you did not request it, you can ignore this message."
    )
    if settings.smtp_host:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_tls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    else:
        folder = Path(settings.outbox_dir)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = folder / f"{uuid4().hex}.eml"
        path.write_bytes(message.as_bytes())
        path.chmod(0o600)


def safe_deliver(email, code):
    try:
        deliver(email, code)
    except Exception:
        # Do not leak account existence, codes, credentials or provider responses.
        logging.getLogger("quantlens.recovery").error(
            "Password recovery delivery failed; check mail configuration."
        )


@router.post("/refresh")
def refresh(body: RefreshInput, request: Request):
    protect(request, "refresh", limit=100, seconds=900)
    with SessionLocal() as db:
        return rotate_token(db, body.refresh_token)


@router.post("/password-reset/request", status_code=202)
def request_reset(body: ResetRequest, request: Request, tasks: BackgroundTasks):
    email = str(body.email).lower()
    protect(request, "reset-request", email, limit=5, seconds=3600)
    code = f"{secrets.randbelow(100000000):08d}"
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user:
            db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
            db.add(
                PasswordReset(
                    user_id=user.id,
                    code_hash=code_hash(email, code),
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.reset_minutes),
                )
            )
            db.commit()
            tasks.add_task(safe_deliver, email, code)
    return {"message": "If the account exists, password reset instructions have been sent."}


@router.post("/password-reset/confirm")
def confirm_reset(body: ResetConfirm, request: Request):
    email = str(body.email).lower()
    protect(request, "reset-confirm", email, limit=10, seconds=900)
    invalid = HTTPException(400, "Invalid or expired code. Request a new code if needed.")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        record = (
            db.scalar(select(PasswordReset).where(PasswordReset.user_id == user.id).with_for_update())
            if user
            else None
        )
        if not record or utc(record.expires_at) <= datetime.now(timezone.utc) or record.attempts >= 5:
            raise invalid
        valid = (
            PasswordReset.id == record.id,
            PasswordReset.attempts < 5,
            PasswordReset.expires_at > datetime.now(timezone.utc),
        )
        if not hmac.compare_digest(record.code_hash, code_hash(email, body.code)):
            db.execute(
                update(PasswordReset)
                .where(*valid)
                .values(attempts=PasswordReset.attempts + 1)
                .execution_options(synchronize_session=False)
            )
            db.commit()
            raise invalid
        # Conditional consumption prevents a code being used twice on SQLite too.
        consumed = db.execute(
            delete(PasswordReset).where(*valid).execution_options(synchronize_session=False)
        ).rowcount
        if consumed != 1:
            db.rollback()
            raise invalid
        user.password_hash = passwords.hash(body.password)
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        db.commit()
    return {"message": "Password updated. Sign in with your new password."}
