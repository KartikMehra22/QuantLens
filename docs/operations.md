# Local deployment and operations

Run one API process. Authentication throttling and the job queue are process-local; multiple workers require a shared queue and limiter first. Evaluation inputs, completed results, sync history and auth sessions are durable database records. Startup marks interrupted experiments failed so they can be rerun. Cancellation is checked between rolling model fits.

## Packaged demonstration

Create a private environment file outside version control containing strong `DEPLOY_DATABASE_PASSWORD` and `DEPLOY_JWT_SECRET` values. Generate each using `python3 -c "import secrets; print(secrets.token_hex(32))"`. Use hexadecimal database passwords to avoid URL escaping problems. Never put these values in source or screenshots.

```bash
docker compose --project-name quantlens-packaged --env-file .env.deploy -f compose.deploy.yaml up --build -d
```

The packaged API is available at http://127.0.0.1:8002 and its docs at http://127.0.0.1:8002/docs. Set that server address in the mobile preview. This deployment has its own PostgreSQL volume and does not reuse the development database. It does not publish PostgreSQL or expose the API beyond this computer. Demo mode is off by default; set `DEPLOY_ALLOW_DEMO=true` for a presentation sandbox if needed.

Public hosting needs a chosen host, trusted HTTPS termination, explicit CORS origins, persistent secrets, mail credentials and an operations owner. The included package has not been deployed publicly. The app does not connect to a broker or execute trades.

## Migrations and backups

Startup applies additive Alembic migrations. It adopts only the exact known original seven-table schema when `alembic_version` is missing; unknown schemas fail safely. Set `AUTO_MIGRATE=false` after applying `uv run alembic upgrade head` explicitly in a controlled deployment.

Before upgrades, stop writes and take a database backup. SQLite supports an online backup without copying a live database file:

```bash
cd backend
uv run python -c "import sqlite3; s=sqlite3.connect('quantlens.db'); d=sqlite3.connect('../backups/quantlens.sqlite'); s.backup(d); d.close(); s.close()"
```

Create `backups` privately first (`mkdir -p backups; chmod 700 backups`). PostgreSQL development backup from the repository root:

```bash
docker compose exec -T db pg_dump -U quantlens -d quantlens --format=custom > backups/quantlens.pgdump
chmod 600 backups/quantlens.pgdump
```

For the packaged environment, add its `--project-name`, `--env-file` and `-f` options. Keep encrypted copies off the laptop under your institution's policy. A backup should be restored periodically into a separate empty disposable database, then checked for row counts, foreign-key integrity and authenticated portfolio summaries. Never restore over the active database without an explicit recovery decision. Retain the original until verification passes. JWT secrets must also be retained privately if existing sessions should survive recovery.

## Account recovery and renewal

Access tokens expire after 15 minutes. Refresh tokens expire with their seven-day server session, rotate after each use and are stored as SHA-256 hashes. Reusing a consumed token revokes its session. Logout and password recovery revoke server-side sessions.

Password recovery returns the same 202 response for known and unknown emails, generates an eight-digit code valid for ten minutes, accepts at most five guesses and consumes a valid code once. Codes are HMAC hashed in the database. Configure SMTP for delivered emails. Without SMTP, messages appear in private ignored `backend/.outbox/*.eml`; this mode is for a local demonstration operator, not end-user email delivery. Delivery failures are logged generically. No external recovery email is sent in automated checks.

The in-memory limiter applies both IP and account windows. Use a reverse proxy with its own limits for public hosting; do not trust arbitrary forwarded IP headers. Current deployment starts exactly one worker.

## Data refresh and jobs

Only Yahoo portfolios can opt into daily automatic history refresh. The scheduler checks every 60 seconds while the server runs. Complete holding downloads and aligned-history validation must succeed before switching sources. A benchmark download may fail independently and is reported as unavailable. Failed automatic attempts are recorded and deferred for 24 hours; a manual retry is always available. `last_sync_at` records the last automatic attempt on failure, and the history status distinguishes success.

The single evaluation worker permits one active job per user and at most eight active jobs globally. A restart fails interrupted jobs explicitly; it does not silently reuse partial predictions. Saved JSON exports include dates, returns, holdings, methodology and metrics. Keep these exports private if they describe personal holdings.

## Health and logs

`GET /health` checks database readiness and returns generic 503 on database failure. Each completed HTTP response includes `X-Request-ID`. JSON request logs contain method, path, status, duration and ID; bodies, tokens, emails and query strings are not logged by that middleware. Logs still contain portfolio IDs in paths. Protect and rotate logs. Uvicorn access logs may include query strings; disable them in deployments that pass sensitive parameters.

After stopping the service, verify no evaluation is active and preserve database and secret volumes. Do not run `docker compose down -v` unless you explicitly intend to delete that environment's database.
