# QuantLens

A React Native mobile app for Indian-equity portfolio management, explainable risk analytics, scenario testing and statistical volatility forecasting. Semester-project implementation with local account recovery, saved model experiments and benchmark comparisons.

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

To run with the project's PostgreSQL service instead, start Docker and use `python3 scripts/dev.py --postgres --web`. This starts the database and applies migrations before launching the API. PostgreSQL uses port **55433** by default (`POSTGRES_PORT` overrides it).

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

Open **Server connection** on the login or profile screen, enter `http://YOUR_LAPTOP_LAN_IP:8000`, then test and save. Keep the phone and laptop on the same Wi-Fi. Connection probes send no account tokens; changing servers clears the old session. Development can also infer the Expo host or use `EXPO_PUBLIC_API_URL` as a default. Standalone apps require an explicit reachable server rather than assuming the phone's localhost is the backend.

See [Android preview build](docs/android-build.md) for the manual GitHub APK workflow, Expo Build route, signing scope, and separate preview/production configurations. APK/device execution is a separate validation step from native configuration and JavaScript bundling.

### PostgreSQL and migrations

```bash
# Repository root; Docker must be running
docker compose up -d db

cd backend
# Copy .env.example to .env, then set:
# DATABASE_URL=postgresql+psycopg://quantlens:local-development@localhost:55433/quantlens
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Startup applies Alembic migrations and can adopt only the exact original unversioned schema. Back up existing databases first. Unknown schemas fail safely. For controlled deployment, migrate explicitly and set `AUTO_MIGRATE=false`. See [operations](docs/operations.md).

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
- Alembic baseline, PostgreSQL runtime validation, SQLite/PostgreSQL test matrix and GitHub Actions checks.
- Persistent server connection settings, credential-free readiness probes, preview and production native transport policies.
- Manual GitHub Actions workflow for a standalone internal Android APK.
- Rotating refresh tokens, recovery codes with SMTP or a private local outbox, and authentication throttling.
- Price-only Nifty 50 comparisons on aligned dates, and comparisons across 2–5 owned portfolios.
- Saved asynchronous rolling evaluations with progress, cancellation, charts and reproducible JSON exports.
- Opt-in daily historical refresh, sync history, additive migrations, request logs and local Docker deployment configuration.

Initial catalog: ten NSE equities and two BSE instruments. This is a curated demonstration universe, not the entire exchange catalog. Yahoo bars preserve available open, high, low, close, adjusted close and volume. Synthetic and close-only CSV histories leave unavailable fields null.

## Historical data

Profile → **Download historical market data** retrieves price histories for all portfolio holdings and switches to Yahoo only when the complete refresh validates. Provider failure leaves the original source unchanged. Current-day bars are excluded conservatively, including after market close.

Yahoo access uses the unofficial `yfinance` package and is subject to provider availability and terms. Consult [the yfinance project](https://github.com/ranaroussi/yfinance) and the applicable Yahoo data terms before using or redistributing downloaded observations. The public repository does not bundle downloaded market datasets.

CSV imports require:

```csv
date,close,adjusted_close
2025-01-02,4000,3950
2025-01-03,4020,3970
```

The same format can be imported for `^NSEI` via the API to enable a private CSV benchmark. Import each holding under Profile, then choose **Use imported CSV data**. The API rejects incomplete source switches. Imported CSV histories are private to the portfolio; another user's upload cannot overwrite them. Sector metadata is a curated classification and may need updating.

## Methodology

Current valuation uses current share quantities and quoted closing prices on the latest date common to every holding. Purchase costs are entered manually. Keep quantities and costs consistent with corporate actions. There is no transaction ledger, realized-P&L accounting or automatic corporate-action adjustment of holdings.

Historical analytics simulate today's value weights with daily rebalancing using adjusted-price simple returns. They do not reconstruct the user's actual returns and must not be interpreted as a historically investable strategy. Missing cross-asset observations are excluded without forward filling. Annualization assumes 252 trading days and Sharpe uses a disclosed 6% effective annual risk-free assumption.

Historical VaR uses the empirical inverse CDF of daily losses at 95% confidence. CVaR averages the worst 5% probability mass, including a fractional boundary observation where needed. Both use a one-trading-day horizon. Maximum drawdown includes the initial wealth observation. Undefined ratios/correlations return null instead of infinity.

Forecasts assume a zero conditional mean. EWMA uses lambda 0.94; the historical baseline uses the last 60 squared returns. GARCH is fitted in percentage-return units and its variances are explicitly converted back to decimal-return variance. Displayed forecasts are the square roots of daily variances, annualized for comparability; they are not five-day cumulative risk.

## Forecast evaluation

The Analytics → Evaluation screen runs and saves rolling experiments. Results persist across sign-in and browser reloads. The API supports JSON exports at `/api/v1/portfolios/{id}/evaluations/{run}/export.json`. For a reproducible three-portfolio real-market study, run `uv run python ../experiments/research_study.py` from `backend/` with the intended database configured. It creates a separate research account and caches downloads in ignored `experiments/results`.


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

# PostgreSQL integration: use only the disposable database ending in _test
# From repository root: docker compose --profile test up -d --wait db-test
QUANTLENS_TEST_DATABASE_URL=postgresql+psycopg://quantlens:local-test-only@localhost:55432/quantlens_test uv run pytest -q

cd ../mobile
npm test
npm run typecheck
npm run lint
npx expo export --platform web
```

Tests cover mathematical fixtures, risk-contribution reconciliation, drawdown initialization, forecast scaling and absence of lookahead, account/holding workflows, ownership isolation, private CSV caches, source-switch failures, saved snapshot integrity and exports. SQLite tests use a temporary database and no external market calls. PostgreSQL tests additionally validate NUMERIC precision, JSON queries, timezone-aware timestamps, cascades and migration parity; migration checks use an isolated temporary schema. Readiness tests verify a failed database returns a generic 503. Mobile connection tests cover local/public URL boundaries and credential-free health probes.

## Configuration and scope

See both `.env.example` files. Local startup creates an ignored `.jwt-secret` with restrictive permissions if JWT_SECRET is unset. For deployment set a persistent secret, configure HTTPS and explicit CORS origins, and disable demo access when unnecessary. Demo accounts are disposable local sandbox accounts; automatic cleanup is not implemented.

Core and research workflows are implemented locally. The study compares the same 252 target days after a 504-return rolling training window; numerical results and their limitations are documented in [study results](docs/study-results.md). Browser execution, database checks and native bundling are distinct from physical-device validation. The earlier APK predates this uncommitted completion batch and must be rebuilt when changes are approved for publishing.

Transaction accounting, broker integration, live quotes, automatic corporate-action changes to share quantities, public hosting and store distribution are outside this semester implementation. Android/iOS hardware execution has not been verified. Recovery emails require configured SMTP; local mode uses an operator outbox. See [operations](docs/operations.md), [API reference](docs/api-reference.md) and [database design](docs/database.md).

No investment advice or trade execution. No guaranteed live prices or model performance.
