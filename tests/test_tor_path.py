"""Tor control parsing, torrc fence, and a real SOCKS5 onion CONNECT."""

from __future__ import annotations

import socket
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from rx.fence import UNPRIVATE_UNLESS_TOR, routing_allowed
from rx.fetch import fetch_through_tor, tls_context_for
from rx.isolate import IsolationError, assert_isolated
from rx.policy import is_onion_host
from rx.session import BrowseSession
from rx.tor import TorState, render_torrc
from rx.tor_ctl import parse_bootstrap_progress, parse_circuit_established, query_bootstrap, authenticate
from rx.tor_socks import socks5_connect

ONION = "e" * 56 + ".onion"


class TestControlParse(unittest.TestCase):
    def test_parse_fields(self):
        self.assertTrue(parse_circuit_established("250-status/circuit-established=1\n250 OK"))
        self.assertFalse(parse_circuit_established("250-status/circuit-established=0\n250 OK"))
        self.assertEqual(
            parse_bootstrap_progress('250-status/bootstrap-phase=NOTICE BOOTSTRAP PROGRESS=100 TAG=done'),
            100,
        )
        self.assertIsNone(parse_circuit_established("500"))

    def test_live_control_socket(self):
        cookie = b"\x01\x02\x03\x04"
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def handle():
            conn, _ = srv.accept()
            data = b""
            while b"\n" not in data:
                data += conn.recv(256)
            line = data.decode().strip()
            self.assertTrue(line.upper().startswith("AUTHENTICATE"))
            sent = line.split(" ", 1)[1].strip()
            if sent.lower() != cookie.hex():
                conn.sendall(b"515 Authentication failed\r\n")
                conn.close()
                return
            conn.sendall(b"250 OK\r\n")
            buf = b""
            replies = [
                b"250-status/circuit-established=1\r\n250 OK\r\n",
                b'250-status/bootstrap-phase=NOTICE BOOTSTRAP PROGRESS=100 TAG=done SUMMARY="Done"\r\n250 OK\r\n',
            ]
            sent_i = 0
            while sent_i < 2:
                chunk = conn.recv(512)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf and sent_i < 2:
                    buf = buf.split(b"\n", 1)[1]
                    conn.sendall(replies[sent_i])
                    sent_i += 1
            conn.close()

        thread = threading.Thread(target=handle, daemon=True)
        thread.start()
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        try:
            authenticate(sock, cookie)
            circuit, progress = query_bootstrap(sock)
        finally:
            sock.close()
            srv.close()
        self.assertTrue(circuit)
        self.assertEqual(progress, 100)


class TestTorrc(unittest.TestCase):
    def test_isolated_torrc(self):
        data = Path("/tmp/rx-privacy-browser-torrc-test")
        text = render_torrc(data, 9070, 9071)
        self.assertIn("CookieAuthentication 1", text)
        self.assertIn("SocksPort 127.0.0.1:9070", text)
        self.assertIn("ClientOnly 1", text)
        self.assertNotIn("1080", text)
        self.assertNotIn("shewall", text.lower())

    def test_shewall_path_refused(self):
        with self.assertRaises(IsolationError):
            assert_isolated("/tmp/shewall/rx")

    def test_routing_requires_circuit(self):
        state = TorState(
            socks_listening=True,
            bootstrapped=False,
            bootstrap_progress=40,
            circuit_established=False,
        )
        self.assertFalse(routing_allowed(state))
        state.bootstrapped = True
        state.bootstrap_progress = 100
        state.circuit_established = True
        self.assertTrue(routing_allowed(state))
        state.socks_port = 1080
        self.assertFalse(routing_allowed(state))


class TestSocksOnion(unittest.TestCase):
    def test_connect_sends_onion_hostname_and_http(self):
        body = b"<html><title>Onion Page</title><p>via tor socks</p></html>"
        seen = {}
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def handle():
            conn, _ = srv.accept()
            conn.settimeout(3)
            greeting = b""
            while len(greeting) < 3:
                greeting += conn.recv(8)
            conn.sendall(b"\x05\x00")
            req = b""
            while len(req) < 5:
                req += conn.recv(64)
            self.assertEqual(req[3], 3)
            ln = req[4]
            while len(req) < 5 + ln + 2:
                req += conn.recv(64)
            seen["host"] = req[5 : 5 + ln].decode()
            seen["port"] = int.from_bytes(req[5 + ln : 7 + ln], "big")
            conn.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            http = b""
            while b"\r\n\r\n" not in http:
                http += conn.recv(1024)
            seen["http"] = http.decode("iso-8859-1")
            raw = (
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            conn.sendall(raw)
            conn.close()

        thread = threading.Thread(target=handle, daemon=True)
        thread.start()

        class SocksTor:
            def __init__(self):
                self.state = TorState(
                    socks_listening=True,
                    bootstrapped=True,
                    bootstrap_progress=100,
                    circuit_established=True,
                    socks_port=port,
                )
                self.connects = []

            def refresh(self):
                return self.state

            def connect(self, host, dest_port, timeout=5):
                self.connects.append((host, dest_port))
                if is_onion_host(host):
                    pass
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect(("127.0.0.1", port))
                socks5_connect(sock, host, dest_port)
                return sock

        real_getaddrinfo = socket.getaddrinfo

        def guard(host, *args, **kwargs):
            if isinstance(host, str) and str(host).endswith(".onion"):
                raise AssertionError("local dns for onion: " + host)
            return real_getaddrinfo(host, *args, **kwargs)

        tor = SocksTor()
        session = BrowseSession(tor)
        with patch("socket.getaddrinfo", guard):
            result = session.navigate("http://" + ONION + "/hello")
        self.assertEqual(seen["host"], ONION)
        self.assertEqual(seen["port"], 80)
        self.assertIn(ONION, seen["http"])
        self.assertNotIn("1080", seen["http"])
        self.assertEqual(result.status, "private via tor")
        self.assertTrue(result.fetch)
        self.assertTrue(result.onion)
        self.assertEqual(result.http_status, 200)
        self.assertIn("via tor socks", result.text)
        self.assertEqual(result.title, "Onion Page")
        srv.close()

    def test_onion_tls_context_is_unverified_clearnet_is_not(self):
        import ssl

        onion_ctx = tls_context_for(ONION)
        clear_ctx = tls_context_for("example.com")
        self.assertEqual(onion_ctx.verify_mode, ssl.CERT_NONE)
        self.assertFalse(onion_ctx.check_hostname)
        self.assertEqual(clear_ctx.verify_mode, ssl.CERT_REQUIRED)
        page = fetch_through_tor  # imported for the real path used above
        self.assertTrue(callable(page))


if __name__ == "__main__":
    unittest.main()
