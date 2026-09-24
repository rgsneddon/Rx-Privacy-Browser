"""Minimal Tor control-port client (cookie AUTHENTICATE + GETINFO)."""

from __future__ import annotations

import re
import socket
from pathlib import Path


class ControlError(RuntimeError):
    pass


def parse_circuit_established(text: str) -> bool | None:
    match = re.search(r"status/circuit-established=([01])", text or "")
    if not match:
        return None
    return match.group(1) == "1"


def parse_bootstrap_progress(text: str) -> int | None:
    match = re.search(r"PROGRESS=(\d+)", text or "")
    if not match:
        return None
    return int(match.group(1))


def _read_reply(sock: socket.socket) -> str:
    chunks: list[str] = []
    buf = b""
    while True:
        part = sock.recv(4096)
        if not part:
            break
        buf += part
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            text = line.decode("utf-8", "replace").rstrip("\r")
            chunks.append(text)
            if text.startswith("250 ") or (
                text.startswith("5") and not text.startswith("250-")
            ):
                return "\n".join(chunks)
    return "\n".join(chunks)


def _command(sock: socket.socket, cmd: str) -> str:
    sock.sendall(cmd.encode("utf-8") + b"\r\n")
    return _read_reply(sock)


def authenticate(sock: socket.socket, cookie: bytes | None) -> None:
    if cookie:
        reply = _command(sock, "AUTHENTICATE " + cookie.hex())
    else:
        reply = _command(sock, "AUTHENTICATE")
    if not reply.startswith("250"):
        raise ControlError(reply.strip() or "control auth failed")


def query_bootstrap(sock: socket.socket) -> tuple[bool, int]:
    circuit_txt = _command(sock, "GETINFO status/circuit-established")
    boot_txt = _command(sock, "GETINFO status/bootstrap-phase")
    circuit = parse_circuit_established(circuit_txt)
    progress = parse_bootstrap_progress(boot_txt)
    if circuit is None or progress is None:
        raise ControlError("control reply missing bootstrap fields")
    return circuit, progress


def candidate_cookie_paths() -> list[Path]:
    return [
        Path("/var/lib/tor/control_auth_cookie"),
        Path("/run/tor/control.authcookie"),
        Path("/var/run/tor/control.authcookie"),
        Path.home() / ".tor" / "control_auth_cookie",
    ]


def load_cookie(explicit: str | Path | None) -> bytes | None:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path.read_bytes()
        return None
    for path in candidate_cookie_paths():
        try:
            if path.is_file():
                return path.read_bytes()
        except OSError:
            continue
    return None
