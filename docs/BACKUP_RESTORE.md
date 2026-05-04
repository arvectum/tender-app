# BACKUP_RESTORE

Команды:

- `python -m app.cli backup-db`
- `python -m app.cli backup-list`
- `python -m app.cli restore-db --file backups/... --yes`
- `python -m app.cli backup-cleanup --keep-last 14`

Правила:

- В production restore требует `--yes`.
- Перед restore выполняется safety backup.
- Scheduler может делать nightly backup при `BACKUP_ENABLED=true`.
- Через dashboard операции backup/restore доступны только роли `admin`.

Рекомендация перед пилотом:

1. Проверить `doctor` и `db check`.
2. Создать backup перед первым real import.
3. Зафиксировать место хранения backup-файлов и retention policy.
