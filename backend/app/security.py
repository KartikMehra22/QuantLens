from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import AuthSession, User

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = passwords.hash("quantlens-dummy-password")


def issue_token(db: Session, user: User):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.token_minutes)
    session = AuthSession(user_id=user.id, expires_at=expiry)
    db.add(session)
    db.commit()
    token = jwt.encode(
        {"sub": user.id, "sid": session.id, "exp": expiry, "iss": "quantlens", "aud": "quantlens-mobile"},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.token_minutes * 60,
        "user": {"id": user.id, "name": user.name, "email": user.email},
    }


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
        or session.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
    ):
        raise error
    user = db.get(User, session.user_id)
    if not user:
        raise error
    return user, session


def current_user(auth=Depends(current_session)):
    return auth[0]
