# QuantLens

A React Native mobile app for Indian-equity portfolio management, explainable risk analytics, scenario testing and statistical volatility forecasting. Semester-project implementation, v0.1.

## Run locally

Requirements: Node.js **24 LTS**, Python **3.12+**, and [uv](https://docs.astral.sh/uv/). A local SQLite database is the default, so Docker and paid hosting are unnecessary to try the app.

```bash
cd /path/to/QuantLens/backend
uv sync --locked

cd ../mobile
npm ci

cd ..
python3 scripts/dev.py --web
```

Open **http://localhost:8081** and select **Explore the demo**. Each demo visitor receives a separate account and portfolio. All demo observations are deterministic synthetic prices, clearly labelled throughout the app. They are not actual stock quotes or empirical market evidence.

For device development, omit `--web` and use an SDK-compatible Expo development client. The dev script starts both servers; Ctrl+C stops them. If the installed Node major version is unsupported (e.g. 25), the script invokes a cached/downloaded Node 24 runtime through npm without replacing the system runtime.

Or use separate terminals:

```bash
# Terminal 1
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2, with Node 24 active
cd mobile
npm run web
```

The API documentation is at **http://localhost:8000/docs**. If ports 8000/8081 are already occupied, stop the previous QuantLens servers first.

### Physical phone

Keep the phone and laptop on the same Wi-Fi. The app infers the backend host from the Expo development host. If needed, copy `mobile/.env.example` to `mobile/.env` and set `EXPO_PUBLIC_API_URL=http://YOUR_LAPTOP_LAN_IP:8000`, then restart Expo. A standalone release needs an explicitly configured reachable API URL. Native iOS/Android binaries and device testing are separate from the web preview.

### PostgreSQL and migrations

```bash
# Repository root; Docker must be running
docker compose up -d db

cd backend
# Copy .env.example to .env, then set:
# DATABASE_URL=postgresql+psycopg://quantlens:local-development@localhost:5432/quantlens
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Apply the baseline migration to an **empty** database before first server startup. Local startup also creates missing tables for convenience; it does not upgrade existing schemas. If you already bootstrapped the exact v0.1 schema with the server, verify it before marking the baseline with `uv run alembic stamp head`. Future changes should use reviewed Alembic migrations.

## Implemented workflows

- Registration and login with Argon2 password hashes, expiring JWTs and server-revocable login sessions; native tokens in SecureStore, web-preview tokens in sessionStorage.
- Isolated demo access; multiple portfolios; portfolio rename/delete; equity search; holding create/edit/remove.
- Current valuation, invested amount and unrealized P&L in INR; instrument price charts; 1M–3Y hypothetical performance charts.
- Annualized volatility, Sharpe ratio, maximum drawdown, 95% historical VaR and CVaR, annualized geometric growth.
- Allocation, sector exposure, Pearson correlations and component contributions to volatility.
- Uniform and asset-specific shock scenarios, with holding-level losses.
- Historical-variance baseline, EWMA and GARCH(1,1) forecasts across five trading days.
- Saved risk/scenario/forecast snapshots, report detail, CSV export and basic PDF reports; native report sharing.
- Yahoo historical-price adapter, atomic refresh/source switching, source-separated caches and private per-portfolio CSV imports.
- Alembic baseline, optional PostgreSQL Compose service, backend tests and GitHub Actions checks.

Initial catalog: ten NSE equities and two BSE instruments. This is a curated demonstration universe, not the entire exchange catalog. Stored bars currently contain closing and adjusted closing prices rather than complete OHLCV.

## Historical data

Profile → **Download historical market data** retrieves price histories for all portfolio holdings and switches to Yahoo only when the complete refresh validates. Provider failure leaves the original source unchanged. Current-day bars are excluded conservatively, including after market close.

Yahoo access uses the unofficial `yfinance` package and is subject to provider availability and terms. Consult [the yfinance project](https://github.com/ranaroussi/yfinance) and the applicable Yahoo data terms before using or redistributing downloaded observations. The public repository does not bundle downloaded market datasets.

CSV imports require:

```csv
date,close,adjusted_close
2025-01-02,4000,3950
2025-01-03,4020,3970
```

Import each holding under Profile, then choose **Use imported CSV data**. The API rejects incomplete source switches. Imported CSV histories are private to the portfolio; another user's upload cannot overwrite them. Sector metadata is a curated classification and may need updating.

## Methodology

Current valuation uses current share quantities and quoted closing prices on the latest date common to every holding. Purchase costs are entered manually. Keep quantities and costs consistent with corporate actions. There is no transaction ledger, realized-P&L accounting or automatic corporate-action adjustment of holdings.

Historical analytics simulate today's value weights with daily rebalancing using adjusted-price simple returns. They do not reconstruct the user's actual returns and must not be interpreted as a historically investable strategy. Missing cross-asset observations are excluded without forward filling. Annualization assumes 252 trading days and Sharpe uses a disclosed 6% effective annual risk-free assumption.

Historical VaR uses the empirical inverse CDF of daily losses at 95% confidence. CVaR averages the worst 5% probability mass, including a fractional boundary observation where needed. Both use a one-trading-day horizon. Maximum drawdown includes the initial wealth observation. Undefined ratios/correlations return null instead of infinity.

Forecasts assume a zero conditional mean. EWMA uses lambda 0.94; the historical baseline uses the last 60 squared returns. GARCH is fitted in percentage-return units and its variances are explicitly converted back to decimal-return variance. Displayed forecasts are the square roots of daily variances, annualized for comparability; they are not five-day cumulative risk.

## Forecast evaluation

Obtain a portfolio ID from the authenticated API or browser route requests, then run from `backend/`:

```bash
uv run python ../experiments/evaluate.py --portfolio PORTFOLIO_ID --training-window 504 --test-days 60
```

The script performs rolling refits, uses only information preceding each target date, and saves date-aligned inputs, predictions, holdings, assumptions and MAE/RMSE/QLIKE to ignored `experiments/results/`. A 252-day evaluation is available when sufficient observations exist. Targets are squared daily returns: a noisy variance proxy. All error metrics use decimal daily variance. Lower loss is better; GARCH is not assumed to outperform the baseline.

Synthetic data validates the software pipeline only. Academic conclusions about the Indian market require a documented historical dataset, fixed evaluation periods and an explicit discussion of retrospective holdings selection.

## Checks

```bash
cd backend
uv run pytest -q
uv run ruff check app tests migrations

cd ../mobile
npm run typecheck
npm run lint
npx expo export --platform web
```

Tests cover mathematical fixtures, risk-contribution reconciliation, drawdown initialization, forecast scaling and absence of lookahead, account/holding workflows, ownership isolation, private CSV caches, source-switch failures, saved snapshot integrity and exports. Tests use a temporary database and no external market calls.

## Configuration and remaining work

See both `.env.example` files. Local startup creates an ignored `.jwt-secret` with restrictive permissions if JWT_SECRET is unset. For deployment set a persistent secret, configure HTTPS and explicit CORS origins, and disable demo access when unnecessary. Demo accounts are disposable local sandbox accounts; automatic cleanup is not implemented.

This v0.1 does not include password recovery/email delivery, refresh-token rotation, transaction accounting, automatic scheduled data synchronization, benchmark comparisons, a graphical out-of-sample results screen, comprehensive mobile automation or store distribution. Before public hosting, add authentication throttling, operational logging, backups and deployment-specific configuration. Native release builds and PostgreSQL runtime integration require their own validation.

No investment advice or trade execution. No guaranteed live prices or model performance.
