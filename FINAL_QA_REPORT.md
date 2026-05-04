# Final QA Report

## Summary

- date: 2026-05-01
- version: 0.7.0
- APP_MODE: demo
- database backend: sqlite
- result: pass (demo/smoke/QA path)

## Fixed during QA

- Created and maintained `ACCEPTANCE_CHECKLIST.md`.
- Added SAFE REAL RUN controls:
  - `REAL_RUN_MODE`
  - source versioning on purchase updates
  - `decision_status` and non-final review flow
- Added data and finance quality gates:
  - `validate-data`
  - `financial-check`
  - `run-real-pipeline --dry-run`
- Added explainability payload (`explanation_json`) and dashboard/excel surfaces.
- Demo SQLite init-db stabilized (`metadata.create_all` path for demo/development).
- Doctor works in demo SQLite with backend/migration mode diagnostics.
- Smoke-test stabilized for autonomous demo pipeline.
- `seed-demo` is idempotent and robust for empty/invalid numeric values.
- DetachedInstanceError risk removed from CLI job outputs (snapshot DTO flow).
- Added demo network safety for parse/price-search/browser checks.
- Added `env init`, `browser install`, `browser doctor`, `db check/current/upgrade`, `validate-export`, `real-source-check`, `dashboard-snapshot`.
- Replaced deprecated `datetime.utcnow` usage with `utc_now` helper in app models/services/tests.

## Commands executed

- `python -m app.cli doctor` -> PASS
- `python -m app.cli init-db` -> PASS
- `python -m app.cli seed-demo` -> PASS
- `python -m app.cli smoke-test` -> PASS
- `python -m app.cli healthcheck` -> PASS
- `python -m app.cli calculate` -> PASS
- `python -m app.cli evaluate` -> PASS
- `python -m app.cli export-excel` -> PASS
- `python -m app.cli validate-export --file exports/tender_small_volume_export.xlsx` -> PASS
- `python -m app.cli browser doctor` -> PASS
- `python -m app.cli real-source-check --source mos_portal --limit 5` (demo/offline) -> PASS (safe skip)
- `pytest` -> 81 passed
- `pytest tests/e2e/` -> 6 passed

## Passed

- Demo quick start and smoke pipeline work with SQLite.
- Dashboard routes are available and auth flow behaves correctly.
- Excel export is generated and validated.
- Test suites pass in offline/demo environment.

## Failed / Known issues

| Area | Issue | Severity | Suggested fix |
|---|---|---|---|
| Production infra | PostgreSQL path and alembic revision checks require real PostgreSQL instance on target host. | medium | Run production checklist on Mac mini with real PostgreSQL and `.env` values. |
| Real sources | `mos_portal/eat` may require auth, captcha handling, and Russian IP. | medium | Use `real-source-check` and browser-login on target network; tune per-source connector settings. |
| Browser state | `data/browser_state/*.json` absent by default until manual login is performed. | low | Run `python -m app.cli browser-login --source ...` in real-network mode. |

## Manual checks required

- real launchd scripts on Mac mini
- production PostgreSQL workflow on target host
- real source checks with Russian IP
- browser-login with real credentials
- manual visual dashboard review in browser
- manual opening of exported Excel files by end users

## Export files

- `exports/tender_small_volume_export.xlsx`
- `exports/decisions.xlsx`
- `exports/smoke_export.xlsx`
- `exports/smoke_decisions.xlsx`

## Documentation status

Updated and relevant:

- `README.md`
- `docs/DEMO_MODE.md`
- `docs/INSTALL_MACOS.md`
- `docs/TROUBLESHOOTING.md`
- `docs/BACKUP_RESTORE.md`
- `docs/SECURITY.md`
- `ACCEPTANCE_CHECKLIST.md`

## Acceptance checklist status

- status: partial pass
- rationale: automated demo/local QA path is stable and passing; production infra and real-site checks remain manual.
