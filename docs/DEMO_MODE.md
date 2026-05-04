# DEMO_MODE

Рекомендуемый старт:

```bash
python -m app.cli env init --mode demo
python -m app.cli doctor
python -m app.cli init-db
python -m app.cli seed-demo
python -m app.cli smoke-test
python -m app.cli run-dashboard
```

Рекомендуемые параметры:

- `APP_MODE=demo`
- `DEMO_DATA_ENABLED=true`
- `REAL_NETWORK_ENABLED=false`
- `DATABASE_URL=sqlite+pysqlite:///data/qa_demo.db`
- `DASHBOARD_SECRET_KEY=qa-demo-secret`
- `NO_PROXY=localhost,127.0.0.1,agregatoreat.ru,.agregatoreat.ru,zakupki.mos.ru,.zakupki.mos.ru,api.zakupki.mos.ru`

SQLite в demo:

- Для SQLite + `APP_MODE=demo/development` используется `SQLAlchemy metadata.create_all`.
- Для PostgreSQL используется Alembic.
- `doctor` показывает backend и migrations mode.

Ограничение сети в demo/offline:

- `parse --source mos_portal` не выполняет реальные запросы.
- `search-prices --mode yandex` завершается сообщением `Real network is disabled in demo mode.`
- `browser-check/browser-login` в offline-режиме сообщают, что сеть отключена.

Полезные команды:

- `python -m app.cli healthcheck`
- `python -m app.cli export-excel`
- `python -m app.cli validate-export --file exports/tender_small_volume_export.xlsx`
- `python -m app.cli dashboard-snapshot --base-url http://127.0.0.1:8000 --username admin --password AdminDemo123!`
