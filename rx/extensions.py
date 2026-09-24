"""Extension permit / load-path resolution for the Rx browser shell.

The on-disk Restore Privacy VPN package is not required to start Rx and is
not a traffic relay. Bootstrap must not call ``load_bundled_vpn``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from rx.fence import UNPRIVATE_UNLESS_TOR, VpnRelayForbidden


# Repo-relative path of the dormant package. Not a bootstrap dependency.
BUNDLED_VPN_REL = Path("extensions") / "restore-privacy-vpn"
# Catalog version of the dormant on-disk package. Not consulted by bootstrap.
ON_DISK_VPN_CATALOG_VERSION = "3.3.3"


@dataclass
class ExtensionInfo:
    id: str
    name: str
    version: str
    path: Path
    enabled: bool = True
    manifest: dict = field(default_factory=dict)

    @property
    def is_bundled_vpn(self) -> bool:
        return "restore privacy vpn" in (self.name or "").lower() or self.id == "restore-privacy-vpn"


class ExtensionRegistry:
    """
    Resolves unpacked extension directories on disk.

    Extensions are off for this vortice. The bundled VPN package may sit on
    disk for inventory, but loading it is refused. Browsing uses Tor only.
    """

    def __init__(self, repo_root: Optional[os.PathLike | str] = None) -> None:
        self.repo_root = Path(repo_root or _default_repo_root()).resolve()
        self.extensions_dir = self.repo_root / "extensions"
        self._loaded: Dict[str, ExtensionInfo] = {}
        # Tor path: do not permit extension load. Bootstrap does not flip this on.
        self.extensions_permitted: bool = False

    def bundled_vpn_path(self) -> Path:
        return (self.repo_root / BUNDLED_VPN_REL).resolve()

    def resolve_extension_path(self, name_or_path: str) -> Path:
        """Resolve a load path: absolute, relative to repo, or under extensions/."""
        if not self.extensions_permitted:
            raise PermissionError("browser extensions are not permitted in this profile")
        p = Path(name_or_path)
        if p.is_absolute() and p.is_dir():
            return p.resolve()
        candidate = (self.repo_root / name_or_path).resolve()
        if candidate.is_dir():
            return candidate
        under = (self.extensions_dir / name_or_path).resolve()
        if under.is_dir():
            return under
        # Allow bare id "restore-privacy-vpn"
        under2 = (self.extensions_dir / Path(name_or_path).name).resolve()
        if under2.is_dir():
            return under2
        raise FileNotFoundError(f"extension path not found: {name_or_path}")

    def _is_bundled_vpn(self, path: Path) -> bool:
        if path.name == "restore-privacy-vpn":
            return True
        try:
            return path.resolve() == self.bundled_vpn_path()
        except OSError:
            return False

    def load_unpacked(self, name_or_path: str, enable: bool = True) -> ExtensionInfo:
        if not self.extensions_permitted:
            raise PermissionError("browser extensions are not permitted in this profile")
        path = self.resolve_extension_path(name_or_path)
        if self._is_bundled_vpn(path):
            raise VpnRelayForbidden(UNPRIVATE_UNLESS_TOR)
        manifest_path = path / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"manifest.json missing in {path}")
        with open(manifest_path, encoding="utf-8-sig") as f:
            manifest = json.load(f)
        ext_id = path.name
        info = ExtensionInfo(
            id=ext_id,
            name=str(manifest.get("name") or ext_id),
            version=str(manifest.get("version") or ""),
            path=path,
            enabled=enable,
            manifest=manifest,
        )
        self._loaded[ext_id] = info
        return info

    def enable(self, ext_id: str) -> ExtensionInfo:
        info = self._require(ext_id)
        info.enabled = True
        return info

    def disable(self, ext_id: str) -> ExtensionInfo:
        info = self._require(ext_id)
        info.enabled = False
        return info

    def list_loaded(self) -> List[ExtensionInfo]:
        return list(self._loaded.values())

    def get(self, ext_id: str) -> Optional[ExtensionInfo]:
        return self._loaded.get(ext_id)

    def load_bundled_vpn(self) -> ExtensionInfo:
        """Refuse the dormant VPN package. It is not the Rx relay and not required."""
        raise VpnRelayForbidden(UNPRIVATE_UNLESS_TOR)

    def read_vpn_version_pin(self) -> str:
        vpn = self.bundled_vpn_path()
        version_file = vpn / "VERSION"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8-sig").strip()
        manifest = vpn / "manifest.json"
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            return str(data.get("version") or "")
        return ""

    def required_extension_files_present(self, path: Optional[Path] = None) -> List[str]:
        """Return list of missing required entry files (empty if complete)."""
        root = path or self.bundled_vpn_path()
        required = [
            "manifest.json",
            "background.js",
            "popup.html",
            "popup.js",
            "lib/vpn_core.js",
            "lib/proxy_adapter.js",
        ]
        missing = []
        for rel in required:
            if not (root / rel).is_file():
                missing.append(rel)
        return missing

    def _require(self, ext_id: str) -> ExtensionInfo:
        if ext_id not in self._loaded:
            raise KeyError(f"extension not loaded: {ext_id}")
        return self._loaded[ext_id]


def _default_repo_root() -> Path:
    # rx/extensions.py -> repo root
    return Path(__file__).resolve().parent.parent
