"""Browse session. Network navigation is refused unless Tor is routing."""

from __future__ import annotations

from dataclasses import dataclass

from rx.fence import (
    PRIVATE_VIA_TOR,
    TRAFFIC_RELAY,
    UNPRIVATE_UNLESS_TOR,
    VPN_RELAY,
    TorUnavailable,
    routing_allowed,
)
from rx.fetch import Page, PolicyStop, fetch_through_tor
from rx.policy import classify_url, is_tracker_host
from rx.tor import null_tor


@dataclass
class NavResult:
    allowed: bool
    blocked: bool
    fetch: bool
    status: str
    private: bool
    url: str
    reason: str = ""
    onion: bool = False
    http_status: int | None = None
    title: str = ""
    text: str = ""
    content_type: str = ""
    tls_verified: bool = False
    vpn_relay: bool = False
    relay: str = TRAFFIC_RELAY


class BrowseSession:
    def __init__(self, tor=None, fetcher=None) -> None:
        self.tor = null_tor() if tor is None else tor
        self.fetcher = fetcher

    def refresh(self):
        refresh = getattr(self.tor, "refresh", None)
        if callable(refresh):
            return refresh()
        return self.tor.state

    def private(self) -> bool:
        self.refresh()
        return routing_allowed(self.tor.state)

    def status_line(self) -> str:
        if self.private():
            return PRIVATE_VIA_TOR
        return UNPRIVATE_UNLESS_TOR

    def status_payload(self) -> dict:
        self.refresh()
        state = self.tor.state
        routing = routing_allowed(state)
        return {
            "routing": routing,
            "private": routing,
            "bootstrapped": bool(state.bootstrapped and state.bootstrap_progress >= 100),
            "bootstrapProgress": int(state.bootstrap_progress or 0),
            "circuitEstablished": bool(state.circuit_established),
            "socksListening": bool(state.socks_listening),
            "socksHost": str(state.socks_host or ""),
            "socksPort": int(state.socks_port or 0),
            "vpnRelay": False if routing else bool(state.vpn_relay),
            "relay": TRAFFIC_RELAY,
            "status": PRIVATE_VIA_TOR if routing else UNPRIVATE_UNLESS_TOR,
            "galleryReady": False,
        }

    def navigate(self, raw: str) -> NavResult:
        routing = self.private()
        status = PRIVATE_VIA_TOR if routing else UNPRIVATE_UNLESS_TOR
        classified = classify_url(raw)
        if not classified.ok:
            return NavResult(
                False, True, False, status, routing, "", classified.reason, False
            )
        if not classified.network:
            return NavResult(
                True, False, False, status, routing, classified.url, "local", False
            )
        if not routing:
            return NavResult(
                False,
                True,
                False,
                UNPRIVATE_UNLESS_TOR,
                False,
                classified.url,
                "tor-down",
                classified.onion,
            )
        if is_tracker_host(classified.host):
            return NavResult(
                False,
                True,
                False,
                PRIVATE_VIA_TOR,
                True,
                classified.url,
                "tracker-blocked",
                classified.onion,
            )
        try:
            page = self._fetch(classified.url)
        except PolicyStop as exc:
            still = self.private()
            return NavResult(
                False,
                True,
                False,
                PRIVATE_VIA_TOR if still else UNPRIVATE_UNLESS_TOR,
                still,
                classified.url,
                exc.reason or "policy",
                classified.onion,
            )
        except TorUnavailable:
            return NavResult(
                False,
                True,
                False,
                UNPRIVATE_UNLESS_TOR,
                False,
                classified.url,
                "tor-down",
                classified.onion,
            )
        except (TimeoutError, OSError):
            still = self.private()
            return NavResult(
                False,
                True,
                False,
                PRIVATE_VIA_TOR if still else UNPRIVATE_UNLESS_TOR,
                still,
                classified.url,
                "tor-fetch-failed",
                classified.onion,
            )
        if not isinstance(page, Page):
            page = Page(
                url=classified.url,
                http_status=int(getattr(page, "http_status", 0) or 0),
                title=str(getattr(page, "title", "") or ""),
                text=str(getattr(page, "text", "") or ""),
                content_type=str(getattr(page, "content_type", "") or ""),
                tls_verified=bool(getattr(page, "tls_verified", False)),
                onion=classified.onion,
            )
        return NavResult(
            True,
            False,
            True,
            PRIVATE_VIA_TOR,
            True,
            page.url or classified.url,
            classified.reason,
            page.onion,
            page.http_status,
            page.title,
            page.text,
            page.content_type,
            page.tls_verified,
            VPN_RELAY,
            TRAFFIC_RELAY,
        )

    def _fetch(self, url: str) -> Page:
        if self.fetcher is not None:
            return self.fetcher(url, self.tor)
        return fetch_through_tor(url, self.tor)
