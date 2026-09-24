"""Rx browser shell bootstrap — original chrome wiring (tabs, privacy, extensions)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rx.extensions import ExtensionRegistry, ExtensionInfo
from rx.fence import TRAFFIC_RELAY, UNPRIVATE_UNLESS_TOR, VpnRelayForbidden
from rx.privacy import PrivacyDefaults, default_privacy
from rx.session import BrowseSession, NavResult
from rx.tabs import TabManager, Tab
from rx.tor import null_tor


@dataclass
class ShellState:
    """In-memory shell state exposed to UI and tests."""

    privacy: PrivacyDefaults
    tabs: TabManager
    extensions: ExtensionRegistry
    bundled_vpn: Optional[ExtensionInfo] = None
    started: bool = False
    vpn_relay: bool = False
    last_nav: Optional[NavResult] = None
    messages: List[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class RxShell:
    """
    From-scratch Rx browser shell.

    Owns the tab session and Tor gate. The bundled VPN extension is not
    loaded and is not required for bootstrap. GUI hosts consume this.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        privacy: Optional[PrivacyDefaults] = None,
        tor=None,
    ) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parent.parent).resolve()
        self.privacy = privacy or default_privacy()
        self.privacy.assert_fence()
        self.tabs = TabManager(start_url=self.privacy.start_url)
        self.extensions = ExtensionRegistry(self.repo_root)
        self.extensions.extensions_permitted = False
        self.session = BrowseSession(null_tor() if tor is None else tor)
        self.state = ShellState(
            privacy=self.privacy,
            tabs=self.tabs,
            extensions=self.extensions,
            vpn_relay=False,
        )

    @property
    def product_banner(self) -> str:
        return self.privacy.banner_line()

    @property
    def window_title(self) -> str:
        active = self.tabs.active_tab
        title = active.title if active else None
        return self.privacy.window_title(title)

    def bootstrap(self) -> ShellState:
        """Start the shell. Does not look for or load the bundled VPN extension."""
        self.privacy.assert_fence()
        self.extensions.extensions_permitted = False
        self.extensions._loaded.clear()
        self.state.bundled_vpn = None
        self.state.vpn_relay = False
        self.state.started = True
        self.state.log(self.product_banner)
        self.state.log(f"status={self.session.status_line()}")
        self.state.log("relay=tor vpn_relay=false")
        self.state.log(f"start_url={self.privacy.start_url} tabs={self.tabs.tab_count()}")
        return self.state

    def open_tab(self, url: Optional[str] = None) -> Tab:
        raw = url if url is not None else self.privacy.start_url
        return self.tabs.open_tab(url=self.privacy.normalize_url(raw))

    def switch_tab(self, tab_id: int) -> Tab:
        return self.tabs.switch_tab(tab_id)

    def close_tab(self, tab_id: int) -> Optional[Tab]:
        return self.tabs.close_tab(tab_id)

    def navigate(self, url: str) -> NavResult:
        result = self.session.navigate(url)
        self.state.last_nav = result
        if result.allowed and not result.blocked:
            tab = self.tabs.navigate_active(result.url)
            if result.title:
                tab.title = result.title
            elif result.url.startswith("about:"):
                tab.title = "New Tab"
        return result

    def reload(self) -> Optional[NavResult]:
        tab = self.tabs.active_tab
        if tab is None:
            return None
        result = self.session.navigate(tab.url)
        self.state.last_nav = result
        if result.allowed and not result.blocked:
            if tab.url != result.url:
                self.tabs.navigate_active(result.url)
            if result.title:
                self.tabs.active_tab.title = result.title
        return result

    def go_back(self) -> Optional[NavResult]:
        tab = self.tabs.active_tab
        if tab is None or not tab.history:
            return None
        result = self.session.navigate(tab.history[-1])
        self.state.last_nav = result
        if result.blocked or not result.allowed:
            return result
        self.tabs.go_back()
        return result

    def go_forward(self) -> Optional[NavResult]:
        tab = self.tabs.active_tab
        if tab is None or not tab.forward:
            return None
        result = self.session.navigate(tab.forward[-1])
        self.state.last_nav = result
        if result.blocked or not result.allowed:
            return result
        self.tabs.go_forward()
        return result

    def enable_extension(self, ext_id: str) -> ExtensionInfo:
        """Extensions are not the traffic path. The bundled VPN cannot be enabled."""
        if ext_id == "restore-privacy-vpn" or "vpn" in ext_id.lower():
            raise VpnRelayForbidden(UNPRIVATE_UNLESS_TOR)
        raise PermissionError("browser extensions are not permitted on the Tor path")

    def snapshot(self) -> Dict[str, Any]:
        active = self.tabs.active_tab
        return {
            "product": self.privacy.product_name,
            "window_title": self.window_title,
            "banner": self.product_banner,
            "started": self.state.started,
            "status": self.session.status_line(),
            "traffic_relay": TRAFFIC_RELAY,
            "vpn_relay": False,
            "gallery_ready": False,
            "privacy": self.privacy.as_dict(),
            "active_tab": (
                {"id": active.id, "title": active.title, "url": active.url}
                if active
                else None
            ),
            "tabs": [
                {"id": t.id, "title": t.title, "url": t.url} for t in self.tabs.tabs
            ],
            "extensions_permitted": self.extensions.extensions_permitted,
            "extensions": [
                {
                    "id": e.id,
                    "name": e.name,
                    "version": e.version,
                    "enabled": e.enabled,
                    "path": str(e.path),
                }
                for e in self.extensions.list_loaded()
            ],
        }

    def smoke_report(self) -> str:
        """Human-readable smoke output for launch verification (includes Rx identity)."""
        if not self.state.started:
            self.bootstrap()
        snap = self.snapshot()
        lines = [
            f"=== {snap['window_title']} ===",
            snap["banner"],
            f"status={snap['status']}",
            f"relay={snap['traffic_relay']}",
            "vpn_relay=false",
            f"started={snap['started']}",
            f"tabs={len(snap['tabs'])} active={snap['active_tab']}",
            f"extensions_permitted={snap['extensions_permitted']}",
            f"extensions={json.dumps(snap['extensions'], indent=2)}",
            "smoke_ok",
        ]
        return "\n".join(lines)


def create_shell(repo_root: Optional[Path] = None, tor=None) -> RxShell:
    return RxShell(repo_root=repo_root, tor=tor)
