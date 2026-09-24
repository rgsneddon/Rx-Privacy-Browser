"""Keep the browser profile and Tor data away from shewall material."""

from __future__ import annotations

import os
from pathlib import Path

_DENY = ("shewall", "shear-wallet", "shear_wallet")


class IsolationError(RuntimeError):
    pass


def assert_isolated(path: os.PathLike | str) -> Path:
    resolved = Path(path).expanduser().resolve()
    low = str(resolved).lower()
    for bad in _DENY:
        if bad in low:
            raise IsolationError(
                f"refusing browser path that overlaps Shear wallet material: {resolved}"
            )
    return resolved


def state_dir() -> Path:
    override = os.environ.get("RX_STATE_DIR", "").strip()
    if override:
        root = assert_isolated(override)
    else:
        root = assert_isolated(Path.home() / ".local" / "share" / "rx-privacy-browser")
    root.mkdir(parents=True, exist_ok=True)
    return root
