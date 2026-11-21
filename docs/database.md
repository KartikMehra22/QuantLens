# Database design

SQLAlchemy models are the schema authority; Alembic revisions 0001–0003 reproduce and reverse the schema. PostgreSQL is the primary relational target; SQLite supports a local demo and parity checks. UUID strings identify user resources. All user-specific queries enforce ownership before loading related data.

| Table | Columns and constraints |
| --- | --- |
| instruments | id: VARCHAR(30) PK; symbol: VARCHAR(30); name: VARCHAR(100); exchange: VARCHAR(10); sector: VARCHAR(50); color: VARCHAR(10) |
| users | id: VARCHAR(36) PK; email: VARCHAR(254); name: VARCHAR(80); password_hash: VARCHAR(255) |
| password_resets | id: VARCHAR(36) PK; user_id: VARCHAR(36) FK users.id; code_hash: VARCHAR(64); expires_at: DATETIME; attempts: INTEGER |
| portfolios | id: VARCHAR(36) PK; user_id: VARCHAR(36) FK users.id; name: VARCHAR(80); data_mode: VARCHAR(20); created_at: DATETIME; auto_sync: BOOLEAN; last_sync_at: DATETIME nullable |
| price_bars | id: INTEGER PK; instrument_id: VARCHAR(30) FK instruments.id; date: DATE; close: NUMERIC(22, 8); adjusted_close: NUMERIC(22, 8); source: VARCHAR(80); open: NUMERIC(22, 8) nullable; high: NUMERIC(22, 8) nullable; low: NUMERIC(22, 8) nullable; volume: NUMERIC(24, 0) nullable |
| sessions | id: VARCHAR(36) PK; user_id: VARCHAR(36) FK users.id; expires_at: DATETIME |
| analysis_runs | id: VARCHAR(36) PK; portfolio_id: VARCHAR(36) FK portfolios.id; kind: VARCHAR(25); created_at: DATETIME; payload: JSON |
| data_sync_runs | id: VARCHAR(36) PK; portfolio_id: VARCHAR(36) FK portfolios.id; status: VARCHAR(20); created_at: DATETIME; instruments: INTEGER; message: VARCHAR(300) |
| forecast_evaluations | id: VARCHAR(36) PK; portfolio_id: VARCHAR(36) FK portfolios.id; status: VARCHAR(20); progress: INTEGER; total: INTEGER; created_at: DATETIME; payload: JSON; error: VARCHAR(300) nullable |
| holdings | id: VARCHAR(36) PK; portfolio_id: VARCHAR(36) FK portfolios.id; instrument_id: VARCHAR(30) FK instruments.id; quantity: NUMERIC(20, 6); average_cost: NUMERIC(20, 6) |
| refresh_tokens | id: VARCHAR(36) PK; session_id: VARCHAR(36) FK sessions.id; token_hash: VARCHAR(64); expires_at: DATETIME; used_at: DATETIME nullable |

Holdings are unique per portfolio and instrument, with positive quantity and average cost. Price bars are unique by instrument, date and source; `csv:{portfolio_id}` isolates imported histories. Missing OHLCV values are null. Cash amounts and quantities use NUMERIC; computational analytics use NumPy float64. Foreign-key cascades remove child holdings, analyses and sessions with their parent resources.

Saved analyses share `analysis_runs` with a kind discriminator; saved rolling studies use `forecast_evaluations` for progress and immutable input snapshots. This is an implementation simplification of the proposal's separate risk, forecast and stress tables. No transaction ledger or historical account valuation table is claimed.
