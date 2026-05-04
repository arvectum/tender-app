# SECURITY

Production требования:

- `APP_MODE=production`
- `DASHBOARD_AUTH_ENABLED=true`
- `DASHBOARD_SECRET_KEY` не должен быть `change-me` и тестовым значением
- PostgreSQL в `DATABASE_URL`

Auth/roles:

- Роли: `admin`, `operator`, `viewer`.
- `viewer` не может менять данные.
- `operator` не может управлять пользователями.
- Backup/restore через dashboard доступны только `admin`.

Технические меры:

- Пароли: PBKDF2 hash (`app/security/password.py`).
- Session cookie: `httpOnly`, `samesite=lax`, `secure` в production.
- CSRF: проверка origin/referer или `X-CSRF-Token`.
- Секреты маскируются через `app/security/redaction.py`.

Demo/offline безопасность:

- При `APP_MODE=demo` и `REAL_NETWORK_ENABLED=false` реальные внешние запросы блокируются.
- Команды реальных источников должны запускаться вручную и осознанно.
