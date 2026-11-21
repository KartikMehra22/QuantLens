# API reference

Open the running API at `http://127.0.0.1:8000/docs` for interactive schemas. The checked-in `openapi.json` records the current endpoint contract. Every user resource requires bearer authentication and an ownership check. Errors use FastAPI `detail`; a missing or unowned resource returns 404. The API sends no auth tokens in connection probes.

| Method | Path | Summary |
| --- | --- | --- |
| POST | `/api/v1/auth/refresh` | Refresh |
| POST | `/api/v1/auth/password-reset/request` | Request Reset |
| POST | `/api/v1/auth/password-reset/confirm` | Confirm Reset |
| POST | `/api/v1/portfolios/{portfolio_id}/evaluations` | Create Evaluation |
| GET | `/api/v1/portfolios/{portfolio_id}/evaluations` | List Evaluations |
| GET | `/api/v1/portfolios/{portfolio_id}/evaluations/{ident}` | Evaluation Detail |
| DELETE | `/api/v1/portfolios/{portfolio_id}/evaluations/{ident}` | Cancel Evaluation |
| GET | `/api/v1/portfolios/{portfolio_id}/evaluations/{ident}/export.json` | Export Evaluation |
| PATCH | `/api/v1/portfolios/{portfolio_id}/settings` | Sync Settings |
| GET | `/api/v1/portfolios/{portfolio_id}/sync-history` | Sync History |
| GET | `/api/v1/portfolio-comparison` | Compare Portfolios |
| GET | `/health` | Health |
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/demo` | Demo |
| GET | `/api/v1/auth/me` | Me |
| PATCH | `/api/v1/auth/me` | Update Profile |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/portfolios` | Portfolios |
| POST | `/api/v1/portfolios` | Create Portfolio |
| PATCH | `/api/v1/portfolios/{portfolio_id}` | Update Portfolio |
| DELETE | `/api/v1/portfolios/{portfolio_id}` | Delete Portfolio |
| GET | `/api/v1/instruments/search` | Search |
| GET | `/api/v1/instruments/{instrument_id}/prices` | Instrument Prices |
| GET | `/api/v1/portfolios/{portfolio_id}/holdings` | List Holdings |
| POST | `/api/v1/portfolios/{portfolio_id}/holdings` | Add Holding |
| PATCH | `/api/v1/portfolios/{portfolio_id}/holdings/{holding_id}` | Edit Holding |
| DELETE | `/api/v1/portfolios/{portfolio_id}/holdings/{holding_id}` | Remove Holding |
| GET | `/api/v1/portfolios/{portfolio_id}/summary` | Summary |
| POST | `/api/v1/portfolios/{portfolio_id}/analyses` | Save Analysis |
| POST | `/api/v1/portfolios/{portfolio_id}/stress-tests` | Scenario |
| POST | `/api/v1/portfolios/{portfolio_id}/forecasts` | Volatility Forecast |
| POST | `/api/v1/portfolios/{portfolio_id}/data-refreshes` | Refresh Prices |
| POST | `/api/v1/portfolios/{portfolio_id}/prices/import` | Import Prices |
| GET | `/api/v1/portfolios/{portfolio_id}/reports` | Reports |
| GET | `/api/v1/portfolios/{portfolio_id}/reports/{run_id}` | Report Detail |
| GET | `/api/v1/portfolios/{portfolio_id}/export.csv` | Export Csv |
| GET | `/api/v1/portfolios/{portfolio_id}/export.pdf` | Export Pdf |
