"""Account recovery, renewable sessions, saved experiments and synchronization history."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("portfolios", sa.Column("auto_sync", sa.Boolean, nullable=False, server_default=sa.false()))
    op.add_column("portfolios", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_table(
        "password_resets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
    op.create_table(
        "forecast_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.Integer, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("error", sa.String(300), nullable=True),
    )
    op.create_index("ix_forecast_evaluations_portfolio_id", "forecast_evaluations", ["portfolio_id"])
    op.create_table(
        "data_sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_id", sa.String(36), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instruments", sa.Integer, nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
    )
    op.create_index("ix_data_sync_runs_portfolio_id", "data_sync_runs", ["portfolio_id"])


def downgrade():
    for name in ["data_sync_runs", "forecast_evaluations", "password_resets", "refresh_tokens"]:
        op.drop_table(name)
    with op.batch_alter_table("portfolios") as batch:
        batch.drop_column("last_sync_at")
        batch.drop_column("auto_sync")
