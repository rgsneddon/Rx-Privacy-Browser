"""SOCKS5 client that sends the destination hostname to Tor (remote DNS)."""

from __future__ import annotations

import ipaddress
import socket


class SocksError(RuntimeError):
    pass


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise SocksError("short socks read")
        buf += chunk
    return buf


def socks5_connect(sock: socket.socket, host: str, port: int) -> None:
    """CONNECT via an already-open SOCKS5 socket. Hostnames are not resolved here."""
    if port < 1 or port > 65535:
        raise SocksError("bad port")
    sock.sendall(b"\x05\x01\x00")
    greeting = _read_exact(sock, 2)
    if greeting != b"\x05\x00":
        raise SocksError("socks auth refused")
    # Typed .onion names stay hostnames. Never hand them to the system resolver.
    if host.lower().rstrip(".").endswith(".onion"):
        ip = None
    else:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
    port_b = int(port).to_bytes(2, "big")
    if isinstance(ip, ipaddress.IPv4Address):
        req = b"\x05\x01\x00\x01" + ip.packed + port_b
    elif isinstance(ip, ipaddress.IPv6Address):
        req = b"\x05\x01\x00\x04" + ip.packed + port_b
    else:
        raw = host.encode("idna")
        if not raw or len(raw) > 255:
            raise SocksError("bad host")
        req = b"\x05\x01\x00\x03" + bytes([len(raw)]) + raw + port_b
    sock.sendall(req)
    hdr = _read_exact(sock, 4)
    if hdr[0] != 5 or hdr[1] != 0:
        raise SocksError(f"socks connect failed: {hdr[1] if len(hdr) > 1 else '?'}")
    atyp = hdr[3]
    if atyp == 1:
        _read_exact(sock, 6)
    elif atyp == 4:
        _read_exact(sock, 18)
    elif atyp == 3:
        ln = _read_exact(sock, 1)[0]
        _read_exact(sock, ln + 2)
    else:
        raise SocksError("bad socks atyp")
