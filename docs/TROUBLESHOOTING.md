# TROUBLESHOOTING

- Нет `.env`: выполните `python -m app.cli env init --mode demo` (или `--mode production`).
- PostgreSQL недоступен: проверьте `DATABASE_URL`, сетевой доступ и права пользователя БД.
- `db check` в production ругается на SQLite: это ожидаемо, production требует PostgreSQL.
- Playwright не установлен: `pip install playwright` и `python -m app.cli browser install`.
- Проверка браузера: `python -m app.cli browser doctor`.
- Dashboard не открывается: `python -m app.cli doctor`, затем `python -m app.cli run-dashboard`.
- Scheduler не стартует: проверьте `SCHEDULER_ENABLED` и `logs/`.
- Парсинг блокируется/капча: используйте `real-source-check`, не обходите капчу, переходите на manual/offline путь.
- Нет цен: `import-offers` + `search-prices --mode manual`.
- Telegram уведомления не работают: проверьте токен/чат id и `NOTIFICATIONS_ENABLED`.
- NO_PROXY: проверьте наличие доменов в `.env`.
- `search-prices --mode yandex` в demo/offline: ожидаемо `Real network is disabled in demo mode.`
- Smoke цепочка: `python -m app.cli smoke-test`, лог `logs/smoke-test.log`.
- Excel проверка: `python -m app.cli validate-export --file exports/tender_small_volume_export.xlsx`.
