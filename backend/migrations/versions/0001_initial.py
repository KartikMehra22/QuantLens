"""Initial QuantLens schema. Static snapshot; local bootstrapping uses the same schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table(
        "portfolios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("data_mode", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])
    op.create_table(
        "instruments",
        sa.Column("id", sa.String(30), primary_key=True),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("sector", sa.String(50), nullable=False),
        sa.Column("color", sa.String(10), nullable=False),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])
    op.create_table(
        "holdings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("instrument_id", sa.String(30), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("average_cost", sa.Numeric(20, 6), nullable=False),
        sa.UniqueConstraint("portfolio_id", "instrument_id"),
        sa.CheckConstraint("quantity > 0"),
        sa.CheckConstraint("average_cost > 0"),
    )
    op.create_index("ix_holdings_portfolio_id", "holdings", ["portfolio_id"])
    op.create_table(
        "price_bars",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(30), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("close", sa.Numeric(22, 8), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(22, 8), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.UniqueConstraint("instrument_id", "date", "source"),
    )
    for column in ("instrument_id", "date", "source"):
        op.create_index(f"ix_price_bars_{column}", "price_bars", [column])
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(25), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.create_index("ix_analysis_runs_portfolio_id", "analysis_runs", ["portfolio_id"])


def downgrade():
    for table in (
        "analysis_runs",
        "price_bars",
        "holdings",
        "instruments",
        "portfolios",
        "sessions",
        "users",
    ):
        op.drop_table(table)
