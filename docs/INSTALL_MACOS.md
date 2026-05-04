# INSTALL_MACOS

## Базовая установка

1. `bash install/macos/install.sh`
2. `python -m app.cli env init --mode production`
3. Отредактировать `.env` (обязательно `DATABASE_URL`, секреты, proxy/no_proxy).
4. `python -m app.cli doctor`
5. `python -m app.cli db upgrade`
6. `python -m app.cli user create --username admin --email admin@example.com --role admin --password 'ChangeMe123!'`
7. `python -m app.cli browser install`
8. `python -m app.cli browser doctor`
9. `bash install/macos/start.sh`
10. `bash install/macos/status.sh`

## Demo check после установки

1. `python -m app.cli env init --mode demo`
2. `python -m app.cli doctor`
3. `python -m app.cli init-db`
4. `python -m app.cli seed-demo`
5. `python -m app.cli smoke-test`

## Важно

- Production: только PostgreSQL + Alembic (`db upgrade`).
- SQLite предназначен только для demo/development.
- Для реальных источников может требоваться российский IP и корректный `NO_PROXY`.
