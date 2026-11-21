import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AuthSession, RefreshToken, User

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = passwords.hash("quantlens-dummy-password")


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def access_token(user, session):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.token_minutes)
    return jwt.encode(
        {"sub": user.id, "sid": session.id, "exp": expiry, "iss": "quantlens", "aud": "quantlens-mobile"},
        settings.jwt_secret,
        algorithm="HS256",
    )


def token_response(db, user, session):
    refresh = secrets.token_urlsafe(48)
    db.add(RefreshToken(session_id=session.id, token_hash=token_hash(refresh), expires_at=session.expires_at))
    db.commit()
    return {
        "access_token": access_token(user, session),
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.token_minutes * 60,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    }


def issue_token(db: Session, user: User):
    session = AuthSession(
        user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_days)
    )
    db.add(session)
    db.flush()
    return token_response(db, user, session)


def rotate_token(db, refresh):
    invalid = HTTPException(401, "Session expired. Please sign in again.")
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(refresh)))
    if not record:
        raise invalid
    session = db.get(AuthSession, record.session_id)
    if not session or utc(record.expires_at) <= datetime.now(timezone.utc):
        raise invalid
    changed = db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == record.id, RefreshToken.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    ).rowcount
    if not changed:
        db.delete(session)
        db.commit()
        raise invalid
    user = db.get(User, session.user_id)
    if not user:
        raise invalid
    return token_response(db, user, session)


def current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
):
    error = HTTPException(401, "Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    if not credentials:
        raise error
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience="quantlens-mobile",
            issuer="quantlens",
            options={"require": ["sub", "sid", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise error from None
    session = db.get(AuthSession, claims["sid"])
    if (
        not session
        or session.user_id != claims["sub"]
        or utc(session.expires_at) <= datetime.now(timezone.utc)
    ):
        raise error
    user = db.get(User, session.user_id)
    if not user:
        raise error
    return user, session


def current_user(auth=Depends(current_session)):
    return auth[0]
