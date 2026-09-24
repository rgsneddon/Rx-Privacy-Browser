"""Hard fences for Rx Privacy Browser.

Traffic relay is Tor circuits only. The bundled Restore Privacy VPN extension
and Shear Privacy VPN are a different product and must not carry this browser.
"""

from __future__ import annotations

UNPRIVATE_UNLESS_TOR = "unprivate unless tor"
PRIVATE_VIA_TOR = "private via tor"

PROGRAM_ID = "rx-privacy-browser-v1"
DISPLAY_NAME = "Rx Privacy Browser"
VORTEX_PERSONAL = "chronoflux-Omega-v1"
VORTICE_KEY_PREFIX = "vort1."

VERSION = "0.2.0"
USER_AGENT = f"RxPrivacyBrowser/{VERSION} (Tor)"

TRAFFIC_RELAY = "tor"
VPN_RELAY = False
# Bundled extension default proxy. Never a Tor circuit.
VPN_PROXY_PORT = 1080

GALLERY_READY = False

EXAMPLE_ORIGIN = (
    "https://rx-privacy-browser.example/vortice/rx-privacy-browser.vortice.json"
)
ORIGIN_URL_PATH = "/vortice/rx-privacy-browser.vortice.json"


class VpnRelayForbidden(RuntimeError):
    def __init__(self, status: str = UNPRIVATE_UNLESS_TOR) -> None:
        super().__init__(status)
        self.status = status


class TorUnavailable(RuntimeError):
    def __init__(self, status: str = UNPRIVATE_UNLESS_TOR) -> None:
        super().__init__(status)
        self.status = status


def reject_vpn_proxy_port(port: int) -> None:
    if int(port) == VPN_PROXY_PORT:
        raise VpnRelayForbidden(UNPRIVATE_UNLESS_TOR)


def routing_allowed(state: object) -> bool:
    """True only when a loopback Tor reports bootstrap 100 and a circuit.

    A listening SOCKS port is not enough. Port 1080 is the VPN extension, not Tor.
    """
    if getattr(state, "vpn_relay", False):
        return False
    try:
        port = int(getattr(state, "socks_port", 0) or 0)
    except (TypeError, ValueError):
        return False
    if port == VPN_PROXY_PORT:
        return False
    host = str(getattr(state, "socks_host", "") or "")
    if host not in {"127.0.0.1", "::1"}:
        return False
    try:
        progress = int(getattr(state, "bootstrap_progress", 0) or 0)
    except (TypeError, ValueError):
        return False
    return bool(
        getattr(state, "socks_listening", False)
        and getattr(state, "bootstrapped", False)
        and progress >= 100
        and getattr(state, "circuit_established", False)
    )
