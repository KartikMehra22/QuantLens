import os
from contextlib import nullcontext
from pathlib import Path

from alembic import command
from alembic.config import Config
from postgres_support import migration_engine
from sqlalchemy import create_engine, inspect


def test_baseline_migration_matches_models_and_reverses(tmp_path):
    database = os.getenv("QUANTLENS_TEST_DATABASE_URL")
    manager = (
        migration_engine(database)
        if database
        else nullcontext(create_engine(f"sqlite:///{tmp_path}/migration.db"))
    )
    with manager as engine:
        check_migration(engine)


def check_migration(engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert {"users", "portfolios", "holdings", "price_bars", "sessions", "analysis_runs"}.issubset(
            inspect(connection).get_table_names()
        )
        command.check(config)
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
