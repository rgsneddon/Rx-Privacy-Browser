"""Rx browser shell bootstrap — original chrome wiring (tabs, privacy, extensions)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rx.extensions import ExtensionRegistry, ExtensionInfo
from rx.privacy import PrivacyDefaults, default_privacy
from rx.tabs import TabManager, Tab


@dataclass
class ShellState:
    """In-memory shell state exposed to UI and tests."""

    privacy: PrivacyDefaults
    tabs: TabManager
    extensions: ExtensionRegistry
    bundled_vpn: Optional[ExtensionInfo] = None
    started: bool = False
    messages: List[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class RxShell:
    """
    From-scratch Rx browser shell.

    Owns tab session, privacy defaults, and extension permit/load for the
    bundled Restore Privacy VPN package. GUI hosts (tk/webview) consume this.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        privacy: Optional[PrivacyDefaults] = None,
    ) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parent.parent).resolve()
        self.privacy = privacy or default_privacy()
        self.privacy.assert_no_telemetry()
        self.tabs = TabManager(start_url=self.privacy.start_url)
        self.extensions = ExtensionRegistry(self.repo_root)
        self.state = ShellState(
            privacy=self.privacy,
            tabs=self.tabs,
            extensions=self.extensions,
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
        """Start shell: enforce privacy defaults, permit extensions, load VPN."""
        self.privacy.assert_no_telemetry()
        if not self.extensions.extensions_permitted:
            raise RuntimeError("extensions must be permitted for Rx VPN bundle")
        missing = self.extensions.required_extension_files_present()
        if missing:
            raise FileNotFoundError(
                f"bundled VPN incomplete under {self.extensions.bundled_vpn_path()}: {missing}"
            )
        vpn = self.extensions.load_bundled_vpn()
        self.state.bundled_vpn = vpn
        self.state.started = True
        self.state.log(self.product_banner)
        self.state.log(
            f"loaded extension {vpn.name} v{vpn.version} from {vpn.path}"
        )
        self.state.log(f"start_url={self.privacy.start_url} tabs={self.tabs.tab_count()}")
        return self.state

    def open_tab(self, url: Optional[str] = None) -> Tab:
        raw = url if url is not None else self.privacy.start_url
        return self.tabs.open_tab(url=self.privacy.normalize_url(raw))

    def switch_tab(self, tab_id: int) -> Tab:
        return self.tabs.switch_tab(tab_id)

    def close_tab(self, tab_id: int) -> Optional[Tab]:
        return self.tabs.close_tab(tab_id)

    def navigate(self, url: str) -> Tab:
        return self.tabs.navigate_active(self.privacy.normalize_url(url))

    def enable_extension(self, ext_id: str) -> ExtensionInfo:
        return self.extensions.enable(ext_id)

    def snapshot(self) -> Dict[str, Any]:
        active = self.tabs.active_tab
        return {
            "product": self.privacy.product_name,
            "window_title": self.window_title,
            "banner": self.product_banner,
            "started": self.state.started,
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
            f"started={snap['started']}",
            f"tabs={len(snap['tabs'])} active={snap['active_tab']}",
            f"extensions_permitted={snap['extensions_permitted']}",
            f"extensions={json.dumps(snap['extensions'], indent=2)}",
            "smoke_ok",
        ]
        return "\n".join(lines)


def create_shell(repo_root: Optional[Path] = None) -> RxShell:
    return RxShell(repo_root=repo_root)
