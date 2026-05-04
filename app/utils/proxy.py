from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import Settings, get_settings


@dataclass(frozen=True)
class ProxyDecision:
    use_proxy: bool
    proxy_url: str | None
    reason: str


class ProxyRouter:
    def __init__(
        self,
        use_proxy: bool,
        http_proxy: str | None,
        https_proxy: str | None,
        no_proxy_hosts: list[str],
    ) -> None:
        self.use_proxy = use_proxy
        self.http_proxy = http_proxy
        self.https_proxy = https_proxy
        self.no_proxy_hosts = [host.lower().strip() for host in no_proxy_hosts if host.strip()]

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "ProxyRouter":
        cfg = settings or get_settings()
        return cls(
            use_proxy=cfg.use_proxy,
            http_proxy=cfg.http_proxy,
            https_proxy=cfg.https_proxy,
            no_proxy_hosts=cfg.no_proxy,
        )

    def should_bypass_proxy(self, url: str) -> bool:
        hostname = (urlparse(url).hostname or "").lower().strip()
        if not hostname:
            return False

        if hostname in {"localhost", "127.0.0.1", "::1"}:
            return True

        for rule in self.no_proxy_hosts:
            if not rule:
                continue
            normalized = rule.lstrip(".")
            if hostname == normalized:
                return True
            if hostname.endswith(f".{normalized}"):
                return True

        return False

    def decide(self, url: str) -> ProxyDecision:
        if not self.use_proxy:
            return ProxyDecision(use_proxy=False, proxy_url=None, reason="proxy_disabled")

        if self.should_bypass_proxy(url):
            return ProxyDecision(use_proxy=False, proxy_url=None, reason="no_proxy_match")

        parsed = urlparse(url)
        proxy_url = self.https_proxy if parsed.scheme == "https" else self.http_proxy
        if proxy_url:
            return ProxyDecision(use_proxy=True, proxy_url=proxy_url, reason="proxy_enabled")

        return ProxyDecision(use_proxy=False, proxy_url=None, reason="proxy_not_configured")

    def requests_proxies_for(self, url: str) -> dict[str, str] | None:
        decision = self.decide(url)
        if not decision.use_proxy or not decision.proxy_url:
            return None

        return {
            "http": self.http_proxy or decision.proxy_url,
            "https": self.https_proxy or decision.proxy_url,
        }

    def httpx_proxy_for(self, url: str) -> str | None:
        decision = self.decide(url)
        return decision.proxy_url if decision.use_proxy else None
