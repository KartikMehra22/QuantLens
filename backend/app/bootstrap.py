"""Apply additive migrations, adopting only the known original unversioned schema."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from .config import settings
from .database import engine

BASELINE = {
    "users": {"id", "email", "name", "password_hash"},
    "sessions": {"id", "user_id", "expires_at"},
    "portfolios": {"id", "user_id", "name", "data_mode", "created_at"},
    "instruments": {"id", "symbol", "name", "exchange", "sector", "color"},
    "holdings": {"id", "portfolio_id", "instrument_id", "quantity", "average_cost"},
    "price_bars": {"id", "instrument_id", "date", "close", "adjusted_close", "source"},
    "analysis_runs": {"id", "portfolio_id", "kind", "created_at", "payload"},
}


def bootstrap_database():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    with engine.begin() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
        if not settings.auto_migrate:
            if current != head:
                raise RuntimeError(
                    "Database migrations are required. Run alembic upgrade head before startup."
                )
            return
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        if current is None and tables:
            inspector = inspect(connection)
            if tables != set(BASELINE) or any(
                {c["name"] for c in inspector.get_columns(table)} != columns
                for table, columns in BASELINE.items()
            ):
                raise RuntimeError(
                    "Unrecognized unversioned schema. Back up and migrate it explicitly before starting."
                )
            command.stamp(config, "0001")
        command.upgrade(config, "head")
