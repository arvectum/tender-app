from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.browser.playwright_factory import build_context_kwargs, open_playwright_browser
from app.config import get_settings


@dataclass
class BrowserCheckResult:
    source: str
    ok: bool
    message: str
    storage_state_path: str


class BrowserSessionManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.browser_storage_state_dir.mkdir(parents=True, exist_ok=True)

    def login(self, source: str) -> BrowserCheckResult:
        source_norm = source.strip().lower()
        start_url, state_path = self._resolve_source(source_norm)
        if not self.settings.real_network_enabled:
            return BrowserCheckResult(
                source=source_norm,
                ok=False,
                message="Real network is disabled in demo mode.",
                storage_state_path=str(state_path),
            )

        context_kwargs = build_context_kwargs(start_url)
        with open_playwright_browser(headless=False) as browser:
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded", timeout=self.settings.playwright_timeout_ms)
            input("Complete login/check manually in opened browser. Press Enter to save session state...")
            context.storage_state(path=str(state_path))
            context.close()

        return BrowserCheckResult(
            source=source_norm,
            ok=True,
            message="storage_state saved",
            storage_state_path=str(state_path),
        )

    def check(self, source: str) -> BrowserCheckResult:
        source_norm = source.strip().lower()
        start_url, state_path = self._resolve_source(source_norm)
        if not self.settings.real_network_enabled:
            return BrowserCheckResult(
                source=source_norm,
                ok=False,
                message="Real network is disabled in demo mode.",
                storage_state_path=str(state_path),
            )

        if not state_path.exists():
            return BrowserCheckResult(
                source=source_norm,
                ok=False,
                message="storage_state file does not exist",
                storage_state_path=str(state_path),
            )

        context_kwargs = build_context_kwargs(start_url)
        context_kwargs["storage_state"] = str(state_path)

        try:
            with open_playwright_browser(headless=True) as browser:
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                page.goto(start_url, wait_until="domcontentloaded", timeout=self.settings.playwright_timeout_ms)
                title = page.title()
                context.close()
            return BrowserCheckResult(
                source=source_norm,
                ok=True,
                message=f"page opened: {title}",
                storage_state_path=str(state_path),
            )
        except Exception as exc:  # noqa: BLE001
            return BrowserCheckResult(
                source=source_norm,
                ok=False,
                message=f"failed to open page: {exc}",
                storage_state_path=str(state_path),
            )

    def state_exists(self, source: str) -> bool:
        _, state_path = self._resolve_source(source.strip().lower())
        return state_path.exists()

    def _resolve_source(self, source: str) -> tuple[str, Path]:
        if source == "mos_portal":
            return self.settings.mos_portal_base_url, self.settings.mos_portal_storage_state
        if source == "eat":
            return self.settings.eat_base_url, self.settings.eat_storage_state
        raise ValueError("source must be mos_portal or eat")
