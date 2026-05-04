from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_init_db_sqlite_demo_mode_uses_create_all(tmp_path: Path) -> None:
    db_path = tmp_path / "qa_demo_init.db"
    db_url = f"sqlite+pysqlite:///{db_path.as_posix()}"

    env = os.environ.copy()
    env.update(
        {
            "APP_MODE": "demo",
            "DEMO_DATA_ENABLED": "true",
            "REAL_NETWORK_ENABLED": "false",
            "DASHBOARD_AUTH_ENABLED": "true",
            "DASHBOARD_SECRET_KEY": "qa-demo-secret",
            "DASHBOARD_ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
            "APP_ENV": "demo",
            "DATABASE_URL": db_url,
            "USE_PROXY": "false",
            "NO_PROXY": "localhost,127.0.0.1,agregatoreat.ru,.agregatoreat.ru,zakupki.mos.ru,.zakupki.mos.ru,api.zakupki.mos.ru",
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "init-db"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Initialized SQLite demo database using SQLAlchemy metadata.create_all." in result.stdout
    assert db_path.exists()
