import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./quantlens.db"
    jwt_secret: str = ""
    token_minutes: int = 60
    cors_origins: str = "http://localhost:8081,http://127.0.0.1:8081,http://localhost:8082"
    allow_demo: bool = True


settings = Settings()
if not settings.jwt_secret:
    # Local-only fallback survives restarts; deployments should set JWT_SECRET explicitly.
    secret_file = Path(".jwt-secret")
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(48))
        secret_file.chmod(0o600)
    settings.jwt_secret = secret_file.read_text().strip()
