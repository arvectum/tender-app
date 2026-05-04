from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.connectors.eat.connector import EatConnector
from app.connectors.mos_portal.connector import MosPortalConnector
from app.config import get_settings
from app.services.import_service import ImportResult, ImportService
from app.utils.logging import get_file_logger


connectors_logger = get_file_logger("connectors.pipeline", "connectors.log")


@dataclass
class ParseReport:
    results: list[ImportResult]

    @property
    def total_found(self) -> int:
        return sum(result.found_count for result in self.results)


def parse_and_import(
    session: Session,
    source: str,
    status: str,
    limit: int | None,
    dry_run: bool,
    save_raw: bool,
) -> ParseReport:
    settings = get_settings()
    if not settings.real_network_enabled or settings.app_mode == "demo":
        return ParseReport(
            results=[
                ImportResult(
                    source=source,
                    skipped_count=1,
                    error_count=1,
                    errors=["Real network is disabled in demo mode."],
                )
            ]
        )

    source = source.strip().lower()
    sources = ["mos_portal", "eat"] if source == "all" else [source]

    results: list[ImportResult] = []
    remaining = limit

    for source_name in sources:
        connector = _make_connector(source_name)
        if connector is None:
            results.append(
                ImportResult(
                    source=source_name,
                    error_count=1,
                    errors=[f"unknown source: {source_name}"],
                )
            )
            continue

        source_limit = remaining
        connectors_logger.info(
            "parse start | source=%s status=%s limit=%s dry_run=%s",
            source_name,
            status,
            source_limit,
            dry_run,
        )
        parsed = connector.fetch_active_purchases(status=status, limit=source_limit)

        import_service = ImportService(session=session, save_raw=save_raw)
        result = import_service.import_purchases(
            source=source_name,
            parsed_purchases=parsed,
            dry_run=dry_run,
            required_status=status,
        )
        results.append(result)

        if remaining is not None:
            remaining = max(remaining - result.found_count, 0)
            if remaining == 0:
                break

    return ParseReport(results=results)


def _make_connector(source: str):
    if source == "mos_portal":
        return MosPortalConnector()
    if source == "eat":
        return EatConnector()
    return None
