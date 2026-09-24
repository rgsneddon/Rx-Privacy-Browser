"""Privacy-focused shell defaults for Rx (pure config, no network I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

from rx.fence import TRAFFIC_RELAY, UNPRIVATE_UNLESS_TOR, VPN_RELAY
from rx.policy import classify_url


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
    # Prefer HTTPS when user omits scheme (bare .onion stays http)
    prefer_https: bool = True
    traffic_relay: str = TRAFFIC_RELAY
    vpn_relay: bool = VPN_RELAY
    status_unprivate: str = UNPRIVATE_UNLESS_TOR

    def window_title(self, page_title: str | None = None) -> str:
        base = f"{self.product_name} — {self.umbrella} Browser"
        if page_title and page_title not in ("New Tab", "about:newtab", ""):
            return f"{page_title} — {base}"
        return base

    def banner_line(self) -> str:
        return (
            f"{self.product_name} Privacy Browser "
            f"(under {self.umbrella}) · telemetry=off · "
            f"tracker_blocking={self.tracker_blocking} · "
            f"relay={self.traffic_relay} · vpn_relay={str(self.vpn_relay).lower()} · "
            f"start={self.start_url}"
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
            "traffic_relay": self.traffic_relay,
            "vpn_relay": self.vpn_relay,
            "status_unprivate": self.status_unprivate,
        }

    def normalize_url(self, raw: str) -> str:
        """Normalize address-bar input. Unsafe schemes collapse to the new tab."""
        got = classify_url(raw, prefer_https=self.prefer_https)
        if not got.ok:
            return self.start_url
        return got.url

    def assert_no_telemetry(self) -> None:
        if self.telemetry_enabled:
            raise AssertionError("telemetry must be disabled in Rx privacy defaults")
        if self.analytics_endpoints:
            raise AssertionError("analytics_endpoints must be empty in Rx shell")

    def assert_fence(self) -> None:
        self.assert_no_telemetry()
        if self.vpn_relay:
            raise AssertionError("VPN relay is forbidden")
        if self.traffic_relay != "tor":
            raise AssertionError("traffic relay must be tor")
        if self.status_unprivate != UNPRIVATE_UNLESS_TOR:
            raise AssertionError("status literal drifted")


def default_privacy() -> PrivacyDefaults:
    return PrivacyDefaults()
