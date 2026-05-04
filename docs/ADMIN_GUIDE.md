# ADMIN_GUIDE

- Управление пользователями: `python -m app.cli user ...`
- Управление стратегиями и правилами через dashboard `/strategies` и `/settings/business-rules`.
- Сервисы: `bash install/macos/start.sh|stop.sh|status.sh`.
- Backup/restore:
  - `python -m app.cli backup-db`
  - `python -m app.cli restore-db --file ... --yes`
- Upgrade:
  - `bash install/macos/upgrade.sh`
