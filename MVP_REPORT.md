# MVP Report

## Status

- MVP status: ready for pilot run
- version: 0.7.0
- date: 2026-05-01
- latest commit: 68f0f5e

## What works

- demo mode on SQLite (`init-db`, `seed-demo`, `smoke-test`)
- doctor and healthcheck
- safe real-run pipeline (`run-real-pipeline --dry-run`)
- data validation (`validate-data`) and financial checks (`financial-check`)
- decision guardrails for risky/low-quality cases
- explainability in decision score (`explanation_json` + summary)
- dashboard pages + auth flow + Next Actions block
- Excel export + validation (with decision/data-quality fields)
- browser setup commands (`browser install`, `browser doctor`)
- safe real-source probe (`real-source-check`)

## Pilot safety

- all real-run decisions are non-final without manual review (`decision_status=needs_review` in REAL_RUN_MODE)
- pricing remains partially manual for stable pilot quality
- requires domain validation before operational usage

## Commands verified

| Command | Result |
|---|---|
| `python -m app.cli doctor` | pass |
| `python -m app.cli smoke-test` | pass |
| `python -m app.cli validate-data` | pass |
| `python -m app.cli financial-check` | pass |
| `python -m app.cli run-real-pipeline --dry-run` | pass |
| `python -m app.cli export-excel` | pass |
| `python -m app.cli validate-export --file exports/tender_small_volume_export.xlsx` | pass |
| `pytest` | 81 passed |
| `pytest tests/e2e/` | 6 passed |

## Dashboard pages verified

| Page | Status | Notes |
|---|---|---|
| `/health` | pass | public endpoint, 200 |
| `/` | pass | includes decision/data-quality and Next Actions |
| `/jobs` | pass | requires login when auth enabled |
| `/diagnostics` | pass | requires login when auth enabled |
| `/risks` | pass | requires login when auth enabled |
| `/watchlist` | pass | requires login when auth enabled |
| `/notifications` | pass | requires login when auth enabled |
| `/reports/daily` | pass | requires login when auth enabled |
| `/suppliers` | pass | requires login when auth enabled |
| `/settings/business-rules` | pass | requires login when auth enabled |
| `/strategies` | pass | requires login when auth enabled |
| `/backups` | pass | requires login when auth enabled |

## Export files

- `exports/tender_small_volume_export.xlsx`
- `exports/real_pipeline_export.xlsx`
- `exports/smoke_export.xlsx`
- `exports/smoke_decisions.xlsx`

## Screenshots

- `artifacts/screenshots/home.png`
- `artifacts/screenshots/purchase_detail.png`
- `artifacts/screenshots/jobs.png`
- `artifacts/screenshots/diagnostics.png`
- `artifacts/screenshots/risks.png`
- `artifacts/screenshots/watchlist.png`
- `artifacts/screenshots/daily_report.png`

## Manual checks still required

- production PostgreSQL workflow on real Mac mini
- real source checks with Russian IP and credentials
- browser-login session creation for real portals
- manual Excel opening/verification by end user
- domain expert approval workflow for decision_status transitions (`approved/rejected`)

## Known warnings

- demo doctor warning about SQLite is expected for demo/development
- `run-real-pipeline --dry-run` with `REAL_NETWORK_ENABLED=false` skips parse step by design

## MVP limitations

- `search-prices --mode yandex` remains semi-automatic/experimental
- for reliable pilot pricing, manual offers import is recommended
- real connectors may require per-site tuning (auth/anti-bot/network)
- no automatic bid submission
- no legal guarantee on procurement outcomes
- no SaaS multi-tenant production packaging in current MVP

## Recommended next steps

1. Configure PostgreSQL on Mac mini and run production bootstrap.
2. Enable `REAL_RUN_MODE=true` and execute first controlled real import.
3. Fill manual offers template for missing prices.
4. Run `validate-data`, `financial-check`, `evaluate`, and review `decision_status`.
5. Confirm first pilot decisions with domain expert.

