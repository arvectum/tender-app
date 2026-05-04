from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


_TRUE_VALUES = {"1", "true", "yes", "on"}
_ALLOWED_SECURITY_MODES = {"standard", "strict"}
_ALLOWED_PRICE_SEARCH_MODES = {"stub", "manual", "yandex"}
_ALLOWED_VAT_MODES = {"included", "excluded", "ignore"}
_ALLOWED_TAX_MODES = {"ignore", "simplified_income", "simplified_income_expense", "general"}
_ALLOWED_DELIVERY_MODES = {"optimistic", "conservative", "strict"}
_ALLOWED_APP_MODES = {"development", "demo", "production"}
_REQUIRED_NO_PROXY_HOSTS = {
    "localhost",
    "127.0.0.1",
    "agregatoreat.ru",
    ".agregatoreat.ru",
    "zakupki.mos.ru",
    ".zakupki.mos.ru",
    "api.zakupki.mos.ru",
}


class ConfigValidationError(ValueError):
    pass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _as_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    return float(value)


def _as_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _as_list(value: str | None, default: list[str] | None = None) -> list[str]:
    if value is None or value.strip() == "":
        return default[:] if default else []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_mode: str
    dashboard_auth_enabled: bool
    dashboard_secret_key: str
    dashboard_allowed_hosts: list[str]
    dashboard_base_url: str
    demo_data_enabled: bool
    real_network_enabled: bool
    real_run_mode: bool

    database_url: str
    use_proxy: bool
    http_proxy: str | None
    https_proxy: str | None
    no_proxy: list[str]
    target_region_codes: list[str]
    min_margin_percent: float
    security_mode: str
    default_unknown_delivery_cost: float
    yandex_find_cheaper_enabled: bool
    google_sheets_enabled: bool
    project_root: Path
    logs_dir: Path

    connector_request_timeout_seconds: float
    connector_user_agent: str
    mos_portal_base_url: str
    mos_portal_api_base_urls: list[str]
    eat_base_url: str
    eat_api_base_urls: list[str]

    price_search_region: str
    price_search_extra_words: list[str]
    min_offer_relevance_score: float
    run_all_price_search_mode: str
    vat_mode: str
    vat_rate: float
    tax_mode: str
    default_markup_percent: float
    delivery_mode: str
    free_delivery_keywords: list[str]
    pickup_allowed: bool
    pickup_cost: float

    scheduler_enabled: bool
    scheduler_timezone: str
    parse_mos_portal_enabled: bool
    parse_eat_enabled: bool
    parse_interval_minutes: int
    price_search_enabled: bool
    price_search_interval_minutes: int
    price_search_mode: str
    calculate_interval_minutes: int
    export_excel_interval_minutes: int
    scheduler_max_instances: int
    scheduler_coalesce: bool

    http_retry_attempts: int
    http_retry_backoff_seconds: float
    http_timeout_seconds: float

    playwright_timeout_ms: int
    playwright_headless: bool
    playwright_slow_mo_ms: int

    browser_storage_state_dir: Path
    mos_portal_storage_state: Path
    eat_storage_state: Path

    notifications_enabled: bool
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    notify_on_recommended: bool
    notify_on_failed_job: bool
    notification_channels: list[str]
    notify_on_strong_recommend: bool
    notify_on_recommend: bool
    notify_on_needs_review: bool
    notify_on_deadline: bool
    notify_daily_digest: bool
    daily_digest_time: str
    daily_digest_timezone: str
    notify_min_margin_percent: float
    notify_min_profit_amount: float
    deadline_warning_hours: list[int]
    deadline_check_interval_minutes: int

    backup_dir: Path
    pg_dump_path: str
    psql_path: str
    backup_enabled: bool
    backup_time: str
    backup_keep_last: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    logs_dir = root / "logs"

    settings = Settings(
        app_mode=os.getenv("APP_MODE", "development"),
        dashboard_auth_enabled=_as_bool(os.getenv("DASHBOARD_AUTH_ENABLED"), default=True),
        dashboard_secret_key=os.getenv("DASHBOARD_SECRET_KEY", "change-me"),
        dashboard_allowed_hosts=_as_list(os.getenv("DASHBOARD_ALLOWED_HOSTS"), default=["127.0.0.1", "localhost"]),
        dashboard_base_url=os.getenv("DASHBOARD_BASE_URL", "http://127.0.0.1:8000"),
        demo_data_enabled=_as_bool(os.getenv("DEMO_DATA_ENABLED"), default=False),
        real_network_enabled=_as_bool(os.getenv("REAL_NETWORK_ENABLED"), default=True),
        real_run_mode=_as_bool(os.getenv("REAL_RUN_MODE"), default=False),
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/tender_small_volume"),
        use_proxy=_as_bool(os.getenv("USE_PROXY"), default=False),
        http_proxy=os.getenv("HTTP_PROXY") or None,
        https_proxy=os.getenv("HTTPS_PROXY") or None,
        no_proxy=_as_list(
            os.getenv("NO_PROXY"),
            default=[
                "localhost",
                "127.0.0.1",
                "agregatoreat.ru",
                ".agregatoreat.ru",
                "zakupki.mos.ru",
                ".zakupki.mos.ru",
                "api.zakupki.mos.ru",
            ],
        ),
        target_region_codes=_as_list(os.getenv("TARGET_REGION_CODES"), default=["77", "50"]),
        min_margin_percent=_as_float(os.getenv("MIN_MARGIN_PERCENT"), default=10.0),
        security_mode=os.getenv("SECURITY_MODE", "standard"),
        default_unknown_delivery_cost=_as_float(os.getenv("DEFAULT_UNKNOWN_DELIVERY_COST"), default=500.0),
        yandex_find_cheaper_enabled=_as_bool(os.getenv("YANDEX_FIND_CHEAPER_ENABLED"), default=False),
        google_sheets_enabled=_as_bool(os.getenv("GOOGLE_SHEETS_ENABLED"), default=False),
        project_root=root,
        logs_dir=logs_dir,
        connector_request_timeout_seconds=_as_float(os.getenv("CONNECTOR_REQUEST_TIMEOUT_SECONDS"), default=10.0),
        connector_user_agent=os.getenv("CONNECTOR_USER_AGENT", "tender-small-volume-calculator/0.4 (+https://localhost)"),
        mos_portal_base_url=os.getenv("MOS_PORTAL_BASE_URL", "https://zakupki.mos.ru"),
        mos_portal_api_base_urls=_as_list(
            os.getenv("MOS_PORTAL_API_BASE_URLS"),
            default=["https://api.zakupki.mos.ru", "https://zakupki.mos.ru/newapi/api"],
        ),
        eat_base_url=os.getenv("EAT_BASE_URL", "https://agregatoreat.ru"),
        eat_api_base_urls=_as_list(
            os.getenv("EAT_API_BASE_URLS"),
            default=["https://agregatoreat.ru/api", "https://agregatoreat.ru/integration/ecom/rest/api"],
        ),
        price_search_region=os.getenv("PRICE_SEARCH_REGION", "Москва"),
        price_search_extra_words=_as_list(os.getenv("PRICE_SEARCH_EXTRA_WORDS"), default=["купить", "цена"]),
        min_offer_relevance_score=_as_float(os.getenv("MIN_OFFER_RELEVANCE_SCORE"), default=0.78),
        run_all_price_search_mode=os.getenv("RUN_ALL_PRICE_SEARCH_MODE", "manual"),
        vat_mode=os.getenv("VAT_MODE", "included"),
        vat_rate=_as_float(os.getenv("VAT_RATE"), default=20.0),
        tax_mode=os.getenv("TAX_MODE", "simplified_income_expense"),
        default_markup_percent=_as_float(os.getenv("DEFAULT_MARKUP_PERCENT"), default=20.0),
        delivery_mode=os.getenv("DELIVERY_MODE", "conservative"),
        free_delivery_keywords=_as_list(os.getenv("FREE_DELIVERY_KEYWORDS"), default=["бесплатная доставка", "доставка бесплатно"]),
        pickup_allowed=_as_bool(os.getenv("PICKUP_ALLOWED"), default=True),
        pickup_cost=_as_float(os.getenv("PICKUP_COST"), default=0.0),
        scheduler_enabled=_as_bool(os.getenv("SCHEDULER_ENABLED"), default=False),
        scheduler_timezone=os.getenv("SCHEDULER_TIMEZONE", "Europe/Moscow"),
        parse_mos_portal_enabled=_as_bool(os.getenv("PARSE_MOS_PORTAL_ENABLED"), default=True),
        parse_eat_enabled=_as_bool(os.getenv("PARSE_EAT_ENABLED"), default=True),
        parse_interval_minutes=_as_int(os.getenv("PARSE_INTERVAL_MINUTES"), default=30),
        price_search_enabled=_as_bool(os.getenv("PRICE_SEARCH_ENABLED"), default=False),
        price_search_interval_minutes=_as_int(os.getenv("PRICE_SEARCH_INTERVAL_MINUTES"), default=60),
        price_search_mode=os.getenv("PRICE_SEARCH_MODE", "manual"),
        calculate_interval_minutes=_as_int(os.getenv("CALCULATE_INTERVAL_MINUTES"), default=30),
        export_excel_interval_minutes=_as_int(os.getenv("EXPORT_EXCEL_INTERVAL_MINUTES"), default=120),
        scheduler_max_instances=_as_int(os.getenv("SCHEDULER_MAX_INSTANCES"), default=1),
        scheduler_coalesce=_as_bool(os.getenv("SCHEDULER_COALESCE"), default=True),
        http_retry_attempts=_as_int(os.getenv("HTTP_RETRY_ATTEMPTS"), default=3),
        http_retry_backoff_seconds=_as_float(os.getenv("HTTP_RETRY_BACKOFF_SECONDS"), default=2.0),
        http_timeout_seconds=_as_float(os.getenv("HTTP_TIMEOUT_SECONDS"), default=30.0),
        playwright_timeout_ms=_as_int(os.getenv("PLAYWRIGHT_TIMEOUT_MS"), default=60000),
        playwright_headless=_as_bool(os.getenv("PLAYWRIGHT_HEADLESS"), default=True),
        playwright_slow_mo_ms=_as_int(os.getenv("PLAYWRIGHT_SLOW_MO_MS"), default=0),
        browser_storage_state_dir=(root / os.getenv("BROWSER_STORAGE_STATE_DIR", "data/browser_state")),
        mos_portal_storage_state=(root / os.getenv("MOS_PORTAL_STORAGE_STATE", "data/browser_state/mos_portal.json")),
        eat_storage_state=(root / os.getenv("EAT_STORAGE_STATE", "data/browser_state/eat.json")),
        notifications_enabled=_as_bool(os.getenv("NOTIFICATIONS_ENABLED"), default=False),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        notify_on_recommended=_as_bool(os.getenv("NOTIFY_ON_RECOMMENDED"), default=True),
        notify_on_failed_job=_as_bool(os.getenv("NOTIFY_ON_FAILED_JOB"), default=True),
        notification_channels=_as_list(os.getenv("NOTIFICATION_CHANNELS"), default=["telegram"]),
        notify_on_strong_recommend=_as_bool(os.getenv("NOTIFY_ON_STRONG_RECOMMEND"), default=True),
        notify_on_recommend=_as_bool(os.getenv("NOTIFY_ON_RECOMMEND"), default=True),
        notify_on_needs_review=_as_bool(os.getenv("NOTIFY_ON_NEEDS_REVIEW"), default=False),
        notify_on_deadline=_as_bool(os.getenv("NOTIFY_ON_DEADLINE"), default=True),
        notify_daily_digest=_as_bool(os.getenv("NOTIFY_DAILY_DIGEST"), default=True),
        daily_digest_time=os.getenv("DAILY_DIGEST_TIME", "09:00"),
        daily_digest_timezone=os.getenv("DAILY_DIGEST_TIMEZONE", "Europe/Moscow"),
        notify_min_margin_percent=_as_float(os.getenv("NOTIFY_MIN_MARGIN_PERCENT"), default=20.0),
        notify_min_profit_amount=_as_float(os.getenv("NOTIFY_MIN_PROFIT_AMOUNT"), default=0.0),
        deadline_warning_hours=[int(x) for x in _as_list(os.getenv("DEADLINE_WARNING_HOURS"), default=["24", "12", "3"])],
        deadline_check_interval_minutes=_as_int(os.getenv("DEADLINE_CHECK_INTERVAL_MINUTES"), default=15),
        backup_dir=(root / os.getenv("BACKUP_DIR", "backups")),
        pg_dump_path=os.getenv("PG_DUMP_PATH", "pg_dump"),
        psql_path=os.getenv("PSQL_PATH", "psql"),
        backup_enabled=_as_bool(os.getenv("BACKUP_ENABLED"), default=True),
        backup_time=os.getenv("BACKUP_TIME", "03:00"),
        backup_keep_last=_as_int(os.getenv("BACKUP_KEEP_LAST"), default=14),
    )

    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    errors: list[str] = []

    if "://" not in settings.database_url:
        errors.append("DATABASE_URL must be a valid SQLAlchemy URL")
    if settings.app_mode not in _ALLOWED_APP_MODES:
        errors.append(f"APP_MODE must be one of: {sorted(_ALLOWED_APP_MODES)}")

    if settings.security_mode not in _ALLOWED_SECURITY_MODES:
        errors.append(f"SECURITY_MODE must be one of: {sorted(_ALLOWED_SECURITY_MODES)}")

    if settings.price_search_mode not in _ALLOWED_PRICE_SEARCH_MODES:
        errors.append(f"PRICE_SEARCH_MODE must be one of: {sorted(_ALLOWED_PRICE_SEARCH_MODES)}")

    if settings.run_all_price_search_mode not in _ALLOWED_PRICE_SEARCH_MODES:
        errors.append(f"RUN_ALL_PRICE_SEARCH_MODE must be one of: {sorted(_ALLOWED_PRICE_SEARCH_MODES)}")
    if settings.vat_mode not in _ALLOWED_VAT_MODES:
        errors.append(f"VAT_MODE must be one of: {sorted(_ALLOWED_VAT_MODES)}")
    if settings.tax_mode not in _ALLOWED_TAX_MODES:
        errors.append(f"TAX_MODE must be one of: {sorted(_ALLOWED_TAX_MODES)}")
    if settings.delivery_mode not in _ALLOWED_DELIVERY_MODES:
        errors.append(f"DELIVERY_MODE must be one of: {sorted(_ALLOWED_DELIVERY_MODES)}")

    missing_no_proxy = [host for host in _REQUIRED_NO_PROXY_HOSTS if host not in settings.no_proxy]
    if missing_no_proxy:
        errors.append(f"NO_PROXY is missing required hosts: {', '.join(sorted(missing_no_proxy))}")

    if settings.scheduler_max_instances < 1:
        errors.append("SCHEDULER_MAX_INSTANCES must be >= 1")

    if settings.http_retry_attempts < 1:
        errors.append("HTTP_RETRY_ATTEMPTS must be >= 1")

    if settings.notifications_enabled:
        if "telegram" in settings.notification_channels and not settings.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required when NOTIFICATIONS_ENABLED=true")
        if "telegram" in settings.notification_channels and not settings.telegram_chat_id:
            errors.append("TELEGRAM_CHAT_ID is required when NOTIFICATIONS_ENABLED=true")
    if settings.deadline_check_interval_minutes < 1:
        errors.append("DEADLINE_CHECK_INTERVAL_MINUTES must be >= 1")
    try:
        hour_part, minute_part = settings.daily_digest_time.split(":")
        hour = int(hour_part)
        minute = int(minute_part)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            errors.append("DAILY_DIGEST_TIME must be in HH:MM 24-hour format")
    except Exception:
        errors.append("DAILY_DIGEST_TIME must be in HH:MM 24-hour format")
    if any(value <= 0 for value in settings.deadline_warning_hours):
        errors.append("DEADLINE_WARNING_HOURS must contain only positive integer values")
    try:
        backup_hour, backup_minute = settings.backup_time.split(":")
        if not (0 <= int(backup_hour) <= 23 and 0 <= int(backup_minute) <= 59):
            errors.append("BACKUP_TIME must be in HH:MM 24-hour format")
    except Exception:
        errors.append("BACKUP_TIME must be in HH:MM 24-hour format")
    if settings.backup_keep_last < 1:
        errors.append("BACKUP_KEEP_LAST must be >= 1")
    if settings.app_mode == "production":
        if settings.dashboard_secret_key.strip() == "change-me":
            errors.append("DASHBOARD_SECRET_KEY must be changed in production")
        if not settings.dashboard_auth_enabled:
            errors.append("DASHBOARD_AUTH_ENABLED must be true in production")

    if errors:
        raise ConfigValidationError("; ".join(errors))


def get_required_no_proxy_hosts() -> set[str]:
    return set(_REQUIRED_NO_PROXY_HOSTS)
