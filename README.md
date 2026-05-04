# tender-small-volume-calculator

Локальный MVP-инструмент для закупок малого объема: импорт закупок, расчет маржи/рисков, принятие решения, Excel-экспорт и dashboard.

## Demo за 5 минут

```bash
python -m app.cli env init --mode demo
python -m app.cli doctor
python -m app.cli init-db
python -m app.cli seed-demo
python -m app.cli calculate
python -m app.cli evaluate
python -m app.cli export-excel
python -m app.cli run-dashboard
```

Открыть dashboard: `http://127.0.0.1:8000`  
Demo admin: `admin / AdminDemo123!`  
Excel export: каталог `exports/`.

## Сценарий 1: Demo (offline-safe)

Рекомендуемые env:

- `APP_MODE=demo`
- `DEMO_DATA_ENABLED=true`
- `REAL_NETWORK_ENABLED=false`
- `REAL_RUN_MODE=false`
- `DATABASE_URL=sqlite+pysqlite:///data/qa_demo.db`

Важно:

- В demo/development SQLite поддерживается через `create_all` (без Alembic).
- В demo с `REAL_NETWORK_ENABLED=false` реальные сетевые запросы блокируются.
- `smoke-test` автономный и не требует внешних сайтов.

## Сценарий 2: Production на Mac mini

```bash
bash install/macos/install.sh
python -m app.cli env init --mode production
# отредактировать .env: DATABASE_URL, секреты, proxy/no_proxy и т.д.
python -m app.cli doctor
python -m app.cli db upgrade
python -m app.cli user create --username admin --email admin@example.com --role admin --password 'ChangeMe123!'
python -m app.cli browser install
python -m app.cli browser doctor
bash install/macos/start.sh
bash install/macos/status.sh
```

Production-путь требует PostgreSQL. SQLite в production не поддерживается.

## Сценарий 3: Первый реальный импорт

```bash
python -m app.cli doctor
python -m app.cli browser doctor
python -m app.cli real-source-check --source mos_portal --limit 5
python -m app.cli run-real-pipeline --dry-run
python -m app.cli export-offer-template --file data/manual_offers_template.xlsx
python -m app.cli import-offers --file data/manual_offers.xlsx
python -m app.cli validate-data
python -m app.cli financial-check
python -m app.cli export-excel
python -m app.cli run-dashboard
```

Примечания MVP:

- Реальные источники могут требовать российский IP и корректный `NO_PROXY`.
- `search-prices --mode yandex` для MVP считается semi-automatic/experimental.
- Для надежного первичного пилота можно использовать manual import цен.

## Основные команды

- `python -m app.cli doctor`
- `python -m app.cli smoke-test`
- `python -m app.cli init-db`
- `python -m app.cli seed-demo`
- `python -m app.cli parse --source mos_portal --limit 20`
- `python -m app.cli search-prices --mode stub`
- `python -m app.cli calculate`
- `python -m app.cli validate-data`
- `python -m app.cli financial-check`
- `python -m app.cli evaluate`
- `python -m app.cli run-real-pipeline --dry-run`
- `python -m app.cli export-excel`
- `python -m app.cli validate-export --file exports/tender_small_volume_export.xlsx`
- `python -m app.cli run-dashboard`
- `python -m app.cli dashboard-snapshot --base-url http://127.0.0.1:8000 --username admin --password AdminDemo123!`

CLI группы:

- `env` (`init`)
- `browser` (`install`, `doctor`)
- `db` (`current`, `upgrade`, `check`)
- `user`, `supplier`, `strategy`, `watchlist`, `demo`, `backup`

## Dashboard страницы

- `/health`
- `/`
- `/jobs`
- `/diagnostics`
- `/risks`
- `/watchlist`
- `/notifications`
- `/reports/daily`
- `/suppliers`
- `/settings/business-rules`
- `/strategies`
- `/backups`

## Где искать артефакты

- Smoke log: `logs/smoke-test.log`
- Excel exports: `exports/`
- Dashboard screenshots: `artifacts/screenshots/`
- QA report: `FINAL_QA_REPORT.md`
- MVP report: `MVP_REPORT.md`
- First run guide: `FIRST_RUN_GUIDE.md`

## Документация

- `docs/INSTALL_MACOS.md`
- `docs/DEMO_MODE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/BACKUP_RESTORE.md`
- `docs/SECURITY.md`
- `docs/OPERATOR_GUIDE.md`
- `docs/ADMIN_GUIDE.md`
- `docs/ROADMAP.md`
