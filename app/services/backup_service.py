from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.utils.time import utc_now


def create_backup() -> Path:
    settings = get_settings()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    output_file = settings.backup_dir / f"tender_calc_{timestamp}.sql"
    db_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    cmd = [settings.pg_dump_path, db_url, "-f", str(output_file)]
    subprocess.run(cmd, check=True)
    return output_file


def list_backups() -> list[Path]:
    settings = get_settings()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    return sorted(settings.backup_dir.glob("tender_calc_*.sql"), reverse=True)


def restore_backup(file_path: Path, yes: bool = False) -> tuple[Path, Path]:
    settings = get_settings()
    if settings.app_mode == "production" and not yes:
        raise ValueError("Production restore requires --yes confirmation")
    if not file_path.exists():
        raise ValueError(f"Backup file not found: {file_path}")
    safety = create_backup()
    db_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    cmd = [settings.psql_path, db_url, "-f", str(file_path)]
    subprocess.run(cmd, check=True)
    return file_path, safety


def cleanup_backups(keep_last: int) -> dict[str, int]:
    files = list_backups()
    to_delete = files[keep_last:]
    removed = 0
    for file in to_delete:
        if file.exists():
            file.unlink()
            removed += 1
    return {"kept": min(keep_last, len(files)), "removed": removed, "total_before": len(files)}


def backup_file_stats() -> list[dict]:
    rows = []
    for file in list_backups():
        rows.append(
            {
                "name": file.name,
                "path": str(file),
                "size_bytes": file.stat().st_size if file.exists() else 0,
                "modified_at": datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc).isoformat() if file.exists() else None,
            }
        )
    return rows
