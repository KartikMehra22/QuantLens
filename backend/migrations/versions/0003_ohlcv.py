"""Preserve available provider OHLCV without inventing it for close-only histories."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    for name in ["open", "high", "low"]:
        op.add_column("price_bars", sa.Column(name, sa.Numeric(22, 8), nullable=True))
    op.add_column("price_bars", sa.Column("volume", sa.Numeric(24, 0), nullable=True))


def downgrade():
    with op.batch_alter_table("price_bars") as batch:
        for name in ["volume", "low", "high", "open"]:
            batch.drop_column(name)
