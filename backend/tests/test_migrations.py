from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_baseline_migration_matches_models_and_reverses(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/migration.db")
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
