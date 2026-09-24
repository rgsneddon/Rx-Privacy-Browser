"""Tor circuit gate. Routing is bootstrap 100 plus circuit-established, not a VPN."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rx.fence import TorUnavailable, routing_allowed
from rx.isolate import assert_isolated, state_dir
from rx.tor_ctl import authenticate, load_cookie, query_bootstrap
from rx.tor_socks import socks5_connect


@dataclass
class TorState:
    socks_listening: bool = False
    bootstrapped: bool = False
    bootstrap_progress: int = 0
    circuit_established: bool = False
    socks_host: str = "127.0.0.1"
    socks_port: int = 9050
    control_host: str = "127.0.0.1"
    control_port: int = 9051
    cookie_path: str = ""
    vpn_relay: bool = False
    message: str = ""


class FlagTor:
    """Test double with an explicit circuit flag. Does not open sockets unless asked."""

    def __init__(self, routing: bool, socks_port: int = 9070) -> None:
        self.state = TorState(
            socks_listening=routing,
            bootstrapped=routing,
            bootstrap_progress=100 if routing else 0,
            circuit_established=routing,
            socks_port=socks_port,
            socks_host="127.0.0.1",
        )
        self.connects: list[tuple[str, int]] = []

    def refresh(self) -> TorState:
        return self.state

    def connect(self, host: str, port: int, timeout: float = 30.0) -> socket.socket:
        self.connects.append((host, port))
        if not routing_allowed(self.state):
            raise TorUnavailable()
        raise TorUnavailable("flag tor has no socks server")


def null_tor() -> FlagTor:
    return FlagTor(False)


def render_torrc(data_dir: Path, socks_port: int, control_port: int) -> str:
    data_dir = assert_isolated(data_dir)
    from rx.fence import reject_vpn_proxy_port

    reject_vpn_proxy_port(socks_port)
    lines = [
        f'DataDirectory "{data_dir}"',
        f"SocksPort 127.0.0.1:{int(socks_port)}",
        f"ControlPort 127.0.0.1:{int(control_port)}",
        "CookieAuthentication 1",
        "ClientOnly 1",
        "SocksPolicy accept 127.0.0.1",
        "SocksPolicy reject *",
        "SafeLogging 1",
        "Log notice stdout",
        "",
    ]
    text = "\n".join(lines)
    low = text.lower()
    if "shewall" in low or "1080" in text:
        raise RuntimeError("torrc failed the relay fence")
    return text


def _tcp_open(host: str, port: int, timeout: float = 0.4) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


class LiveTor:
    """Attach to a local Tor daemon, or spawn one in an isolated data directory."""

    def __init__(self) -> None:
        socks = int(os.environ.get("RX_TOR_SOCKS_PORT", "9050") or "9050")
        control = int(os.environ.get("RX_TOR_CONTROL_PORT", "9051") or "9051")
        self.state = TorState(socks_port=socks, control_port=control)
        cookie = os.environ.get("RX_TOR_COOKIE", "").strip()
        if cookie:
            self.state.cookie_path = cookie
        self.proc: subprocess.Popen | None = None
        self._spawned = False

    def refresh(self) -> TorState:
        host = self.state.socks_host
        self.state.socks_listening = _tcp_open(host, self.state.socks_port)
        self.state.vpn_relay = False
        try:
            info = self._query()
        except (OSError, TimeoutError, RuntimeError):
            self.state.circuit_established = False
            self.state.bootstrapped = False
            if not self.state.message:
                self.state.message = "tor control unavailable"
            return self.state
        self.state.circuit_established = info[0]
        self.state.bootstrap_progress = info[1]
        self.state.bootstrapped = info[1] >= 100
        if routing_allowed(self.state):
            self.state.message = "circuit established"
        else:
            self.state.message = f"bootstrap {info[1]}"
        return self.state

    def _query(self) -> tuple[bool, int]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        sock.connect((self.state.control_host, int(self.state.control_port)))
        try:
            cookie = load_cookie(self.state.cookie_path or None)
            authenticate(sock, cookie)
            return query_bootstrap(sock)
        finally:
            sock.close()

    def connect(self, host: str, port: int, timeout: float = 45.0) -> socket.socket:
        self.refresh()
        if not routing_allowed(self.state):
            raise TorUnavailable()
        from rx.fence import reject_vpn_proxy_port

        reject_vpn_proxy_port(self.state.socks_port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((self.state.socks_host, int(self.state.socks_port)))
            socks5_connect(sock, host, port)
        except Exception:
            sock.close()
            raise
        return sock

    def spawn(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        binary = shutil.which("tor")
        if not binary:
            self.state.message = "tor binary not found"
            return False
        data = assert_isolated(state_dir() / "tor")
        data.mkdir(parents=True, exist_ok=True)
        socks_port = int(os.environ.get("RX_TOR_SPAWN_SOCKS", "9070") or "9070")
        control_port = int(os.environ.get("RX_TOR_SPAWN_CONTROL", "9071") or "9071")
        torrc_path = data / "torrc"
        torrc_path.write_text(render_torrc(data, socks_port, control_port), encoding="utf-8")
        log_handle = open(data / "notice.log", "ab")
        self.proc = subprocess.Popen(
            [binary, "-f", str(torrc_path)],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        self._spawned = True
        self.state.socks_port = socks_port
        self.state.control_port = control_port
        self.state.cookie_path = str(data / "control_auth_cookie")
        self.state.message = "tor starting"
        return True

    def ensure(self) -> TorState:
        self.refresh()
        if routing_allowed(self.state):
            return self.state
        # System tor on 9050/9051 is already what refresh just asked, unless
        # the operator pointed RX_TOR_* elsewhere. Try the well-known pair once
        # before spawning a private daemon.
        if self.state.socks_port != 9050 or self.state.control_port != 9051:
            self.state.socks_port = 9050
            self.state.control_port = 9051
            self.state.cookie_path = ""
            self.refresh()
            if routing_allowed(self.state):
                return self.state
        self.spawn()
        return self.state

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
