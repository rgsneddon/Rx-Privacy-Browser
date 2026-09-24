"""Build the pinned Continuum origin body from the browser UI sources."""

from __future__ import annotations

import json
from pathlib import Path

from rx.fence import DISPLAY_NAME, PROGRAM_ID, UNPRIVATE_UNLESS_TOR, PRIVATE_VIA_TOR
from rx.origin import BROWSER_HTML, ORIGIN_FILE

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "continuum" / "ui"
TEMPLATE = UI / "browser.template.html"


def render_browser_html() -> str:
    css = (UI / "app.css").read_text(encoding="utf-8")
    gate = (UI / "gate.js").read_text(encoding="utf-8")
    app = (UI / "app.js").read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    html = (
        html.replace("__RX_CSS__", css)
        .replace("__RX_GATE__", gate)
        .replace("__RX_APP__", app)
    )
    if "__RX_" in html:
        raise RuntimeError("browser template placeholder left unreplaced")
    if not html.endswith("\n"):
        html += "\n"
    return html


def origin_document(html: str) -> dict:
    return {
        "v": 1,
        "kind": "continuum-dapp",
        "programId": PROGRAM_ID,
        "name": DISPLAY_NAME,
        "galleryReady": False,
        "relay": "tor",
        "vpnRelay": False,
        "statusUnprivate": UNPRIVATE_UNLESS_TOR,
        "statusPrivate": PRIVATE_VIA_TOR,
        "telemetry": False,
        "trackerBlocking": True,
        "isolation": "dedicated-webview-profile",
        "entry": "browser.html",
        "tor": {
            "architecture": "tor-circuits",
            "socks": "socks5h://127.0.0.1:9050",
            "remoteDns": True,
            "failClosed": True,
            "daemon": "tor-or-arti",
        },
        "notVpn": (
            "Restore Privacy VPN and Shear Privacy VPN are not the traffic relay. "
            "This vortice does not route user traffic through them."
        ),
        "hostHooks": {
            "inject": "window.rxHost",
            "requiredForInWalletUi": True,
            "statusMethod": "status",
            "navigateMethod": "navigate",
            "unprivateStatus": UNPRIVATE_UNLESS_TOR,
            "vpnRelay": False,
            "isolatedFromShewall": True,
        },
        "browser.html": html,
    }


def origin_text_from(html: str) -> str:
    return json.dumps(origin_document(html), indent=2, ensure_ascii=False) + "\n"


def pack_bytes() -> tuple[bytes, bytes]:
    html = render_browser_html().encode("utf-8")
    body = origin_text_from(html.decode("utf-8")).encode("utf-8")
    return html, body


def write_pack() -> tuple[Path, Path]:
    html, body = pack_bytes()
    BROWSER_HTML.parent.mkdir(parents=True, exist_ok=True)
    BROWSER_HTML.write_bytes(html)
    ORIGIN_FILE.write_bytes(body)
    return BROWSER_HTML, ORIGIN_FILE


def main() -> int:
    html_path, origin_path = write_pack()
    print(f"wrote {html_path}")
    print(f"wrote {origin_path}")
    print(f"origin_bytes={origin_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
