import secrets
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./quantlens.db"
    jwt_secret: str = ""
    token_minutes: int = 15
    auto_migrate: bool = True
    refresh_days: int = 7
    reset_minutes: int = 10
    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    mail_from: str = "QuantLens <no-reply@quantlens.local>"
    outbox_dir: str = ".outbox"
    rate_limits_enabled: bool = True
    sync_poll_seconds: int = 60
    cors_origins: str = "http://localhost:8081,http://127.0.0.1:8081,http://localhost:8082"
    allow_demo: bool = True

    @field_validator("database_url")
    @classmethod
    def use_psycopg(cls, url: str) -> str:
        if url.startswith(("postgresql://", "postgres://")):
            return "postgresql+psycopg://" + url.split("://", 1)[1]
        return url


settings = Settings()
if not settings.jwt_secret:
    # Local-only fallback survives restarts; deployments should set JWT_SECRET explicitly.
    secret_file = Path(".jwt-secret")
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(48))
        secret_file.chmod(0o600)
    settings.jwt_secret = secret_file.read_text().strip()
