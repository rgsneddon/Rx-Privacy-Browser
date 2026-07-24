"""Privacy-focused shell defaults for Rx (pure config, no network I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass(frozen=True)
class PrivacyDefaults:
    """
    Browser-shell privacy policy.

    - No third-party telemetry / analytics wiring in the shipped shell.
    - Private new-tab start page by default.
    - Tracker-blocking preference enabled by default (shell flag).
    - Do-Not-Track and referrer trimming defaults on.
    """

    product_name: str = "Rx"
    umbrella: str = "Restore Privacy"
    # Start on a private new-tab surface (not a third-party home/search portal)
    start_url: str = "about:newtab"
    start_private: bool = True
    # Shell-level tracker blocking preference (assertable default)
    tracker_blocking: bool = True
    send_do_not_track: bool = True
    trim_referrer: bool = True
    # Explicit: no analytics / crash-telemetry endpoints in the shell
    telemetry_enabled: bool = False
    analytics_endpoints: tuple = ()
    third_party_cookies_default: bool = False
    # Prefer HTTPS when user omits scheme
    prefer_https: bool = True

    def window_title(self, page_title: str | None = None) -> str:
        base = f"{self.product_name} — {self.umbrella} Browser"
        if page_title and page_title not in ("New Tab", "about:newtab", ""):
            return f"{page_title} — {base}"
        return base

    def banner_line(self) -> str:
        return (
            f"{self.product_name} Privacy Browser "
            f"(under {self.umbrella}) · telemetry=off · "
            f"tracker_blocking={self.tracker_blocking} · start={self.start_url}"
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "product_name": self.product_name,
            "umbrella": self.umbrella,
            "start_url": self.start_url,
            "start_private": self.start_private,
            "tracker_blocking": self.tracker_blocking,
            "send_do_not_track": self.send_do_not_track,
            "trim_referrer": self.trim_referrer,
            "telemetry_enabled": self.telemetry_enabled,
            "analytics_endpoints": list(self.analytics_endpoints),
            "third_party_cookies_default": self.third_party_cookies_default,
            "prefer_https": self.prefer_https,
        }

    def normalize_url(self, raw: str) -> str:
        """Normalize address-bar input using privacy-oriented scheme preference."""
        s = (raw or "").strip()
        if not s:
            return self.start_url
        lower = s.lower()
        if lower.startswith("about:") or lower.startswith("file:"):
            return s
        if lower.startswith("http://") or lower.startswith("https://"):
            return s
        if "://" in s:
            return s
        # Bare host / search-ish: prefer HTTPS, never inject a telemetry host
        if " " in s or "." not in s:
            # Local new-tab search placeholder (no third-party search product hardwired)
            from urllib.parse import quote_plus

            return f"about:search?q={quote_plus(s)}"
        if self.prefer_https:
            return f"https://{s}"
        return f"http://{s}"

    def assert_no_telemetry(self) -> None:
        if self.telemetry_enabled:
            raise AssertionError("telemetry must be disabled in Rx privacy defaults")
        if self.analytics_endpoints:
            raise AssertionError("analytics_endpoints must be empty in Rx shell")


def default_privacy() -> PrivacyDefaults:
    return PrivacyDefaults()
