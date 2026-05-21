from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.config import Settings
from app.db import Base, engine


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SQLITE_DEMO_MIGRATION_MODE = "create_all_for_demo"
ALEMBIC_MIGRATION_MODE = "alembic"


def run_migrations() -> None:
    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    command.upgrade(alembic_cfg, "head")


def database_backend(database_url: str) -> str:
    lowered = (database_url or "").strip().lower()
    if lowered.startswith("sqlite"):
        return "sqlite"
    if lowered.startswith("postgresql") or lowered.startswith("postgres"):
        return "postgresql"
    return "unknown"


def migration_mode_for_settings(settings: Settings) -> str:
    backend = database_backend(settings.database_url)
    # SQLite migrations in this project are not fully Alembic-safe (FK ALTER / drifted local DBs).
    # Use model-driven bootstrap for SQLite in all app modes to keep local/prod-lite runs stable.
    if backend == "sqlite":
        return SQLITE_DEMO_MIGRATION_MODE
    return ALEMBIC_MIGRATION_MODE


def ensure_runtime_directories(settings: Settings) -> list[Path]:
    dirs = [
        settings.project_root / "data",
        settings.project_root / "logs",
        settings.project_root / "exports",
        settings.project_root / "backups",
        settings.project_root / "data" / "browser_state",
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def init_database_for_settings(settings: Settings) -> str:
    mode = migration_mode_for_settings(settings)
    if mode == SQLITE_DEMO_MIGRATION_MODE:
        import app.models  # noqa: F401

        if not _sqlite_schema_is_compatible():
            Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return mode

    run_migrations()
    return mode


def alembic_config() -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return cfg


def get_current_revision() -> str | None:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()


def get_head_revision() -> str:
    cfg = alembic_config()
    script = ScriptDirectory.from_config(cfg)
    return str(script.get_current_head())


def migrations_are_up_to_date() -> bool:
    return get_current_revision() == get_head_revision()


def upgrade_head() -> None:
    command.upgrade(alembic_config(), "head")


def _sqlite_schema_is_compatible() -> bool:
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    for table_name, table in Base.metadata.tables.items():
        if table_name not in db_tables:
            return False
        db_columns = {column["name"] for column in inspector.get_columns(table_name)}
        model_columns = {column.name for column in table.columns}
        if not model_columns.issubset(db_columns):
            return False
    return True
