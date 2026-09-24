"""Fail-closed session: no socket and no fetch unless Tor is routing."""

from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from rx.fence import PRIVATE_VIA_TOR, UNPRIVATE_UNLESS_TOR, VPN_PROXY_PORT
from rx.fetch import Page
from rx.onion_smoke import smoke_once
from rx.session import BrowseSession
from rx.tor import FlagTor, null_tor

ONION = "http://" + ("d" * 56) + ".onion/hidden"


class TestSessionFence(unittest.TestCase):
    def test_status_literal_when_tor_down(self):
        session = BrowseSession(null_tor())
        self.assertFalse(session.private())
        self.assertEqual(session.status_line(), UNPRIVATE_UNLESS_TOR)
        payload = session.status_payload()
        self.assertEqual(payload["status"], UNPRIVATE_UNLESS_TOR)
        self.assertFalse(payload["private"])
        self.assertFalse(payload["vpnRelay"])
        self.assertEqual(payload["relay"], "tor")

    def test_onion_and_clearnet_do_not_open_sockets(self):
        session = BrowseSession(null_tor())

        def explode(*_a, **_k):
            raise AssertionError("socket opened while tor is down")

        with patch("socket.socket", explode), patch("socket.getaddrinfo", explode):
            onion = session.navigate(ONION)
            clear = session.navigate("https://example.com/path")
        self.assertTrue(onion.blocked)
        self.assertTrue(onion.onion)
        self.assertFalse(onion.fetch)
        self.assertEqual(onion.status, UNPRIVATE_UNLESS_TOR)
        self.assertTrue(clear.blocked)
        self.assertFalse(clear.fetch)
        self.assertEqual(clear.status, UNPRIVATE_UNLESS_TOR)
        self.assertEqual(session.tor.connects, [])

    def test_vpn_flag_and_proxy_port_are_not_private(self):
        tor = FlagTor(True)
        tor.state.vpn_relay = True
        session = BrowseSession(tor)
        result = session.navigate("https://example.com/")
        self.assertEqual(result.status, UNPRIVATE_UNLESS_TOR)
        self.assertFalse(result.fetch)
        self.assertEqual(tor.connects, [])

        tor_port = FlagTor(True, socks_port=VPN_PROXY_PORT)
        session_port = BrowseSession(tor_port)
        blocked = session_port.navigate(ONION)
        self.assertEqual(blocked.status, UNPRIVATE_UNLESS_TOR)
        self.assertEqual(tor_port.connects, [])

    def test_routing_fetches_onion_through_injected_fetcher_only(self):
        tor = FlagTor(True)
        seen = []

        def fetcher(url, _tor):
            seen.append(url)
            return Page(
                url=url,
                http_status=200,
                title="Hidden",
                text="onion body",
                content_type="text/html",
                tls_verified=False,
                onion=True,
            )

        session = BrowseSession(tor, fetcher=fetcher)
        result = session.navigate(ONION)
        self.assertEqual(result.status, PRIVATE_VIA_TOR)
        self.assertTrue(result.private)
        self.assertTrue(result.fetch)
        self.assertTrue(result.onion)
        self.assertEqual(result.text, "onion body")
        self.assertEqual(seen, [result.url])
        self.assertEqual(tor.connects, [])

    def test_tracker_blocked_without_fetch(self):
        tor = FlagTor(True)
        called = []
        session = BrowseSession(tor, fetcher=lambda *a, **k: called.append(1))
        result = session.navigate("https://doubleclick.net/ad")
        self.assertTrue(result.blocked)
        self.assertEqual(result.reason, "tracker-blocked")
        self.assertEqual(result.status, PRIVATE_VIA_TOR)
        self.assertEqual(called, [])
        self.assertEqual(tor.connects, [])

    def test_smoke_refuses_without_fetch(self):
        lines = []
        session = BrowseSession(null_tor(), fetcher=lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetched")))
        code = smoke_once(session, ONION, out=lines.append)
        self.assertEqual(code, 2)
        self.assertEqual(lines[0], UNPRIVATE_UNLESS_TOR)
        self.assertIn("not_fetched", lines)

    def test_timeout_stays_on_tor_status(self):
        tor = FlagTor(True)

        def fetcher(_url, _tor):
            raise TimeoutError("slow circuit")

        session = BrowseSession(tor, fetcher=fetcher)
        result = session.navigate("https://example.com/")
        self.assertEqual(result.status, PRIVATE_VIA_TOR)
        self.assertTrue(result.private)
        self.assertTrue(result.blocked)
        self.assertFalse(result.fetch)
        self.assertEqual(result.reason, "tor-fetch-failed")

    def test_caption_and_partial_bootstrap_do_not_fetch(self):
        def boom(*_a, **_k):
            raise AssertionError("fetched")

        quiet = FlagTor(True)
        quiet.state.socks_listening = False
        quiet.state.message = PRIVATE_VIA_TOR
        session = BrowseSession(quiet, fetcher=boom)
        result = session.navigate(ONION)
        self.assertEqual(result.status, UNPRIVATE_UNLESS_TOR)
        self.assertFalse(result.fetch)
        self.assertFalse(result.private)
        self.assertEqual(quiet.connects, [])
        payload = session.status_payload()
        self.assertEqual(payload["status"], UNPRIVATE_UNLESS_TOR)
        self.assertEqual(payload["socksHost"], "127.0.0.1")
        self.assertFalse(payload["socksListening"])

        partial = FlagTor(True)
        partial.state.bootstrap_progress = 99
        partial.state.bootstrapped = False
        held = BrowseSession(partial, fetcher=boom)
        blocked = held.navigate("https://example.com/")
        self.assertEqual(blocked.status, UNPRIVATE_UNLESS_TOR)
        self.assertEqual(partial.connects, [])

        remote = FlagTor(True)
        remote.state.socks_host = "10.1.2.3"
        away = BrowseSession(remote, fetcher=boom)
        refused = away.navigate("https://example.com/")
        self.assertEqual(refused.status, UNPRIVATE_UNLESS_TOR)
        self.assertEqual(remote.connects, [])

    def test_secret_paste_is_not_fetched_or_echoed(self):
        session = BrowseSession(null_tor(), fetcher=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("fetched")))
        mnemonic = " ".join(["abandon"] * 11 + ["about"])
        for raw in (mnemonic, "shewall.bin", "ab" * 32, "-----BEGIN PRIVATE KEY-----\nMII\n"):
            result = session.navigate(raw)
            self.assertEqual(result.status, UNPRIVATE_UNLESS_TOR)
            self.assertEqual(result.reason, "secret-refused")
            self.assertEqual(result.url, "")
            self.assertFalse(result.fetch)
            self.assertNotIn(raw, result.reason)
            self.assertNotIn("abandon", result.url)
        clear = session.navigate("https://example.com/")
        self.assertEqual(clear.reason, "tor-down")
        self.assertNotEqual(clear.reason, "secret-refused")

    def test_local_new_tab_needs_no_tor(self):
        session = BrowseSession(null_tor())
        result = session.navigate("about:newtab")
        self.assertTrue(result.allowed)
        self.assertFalse(result.fetch)
        self.assertEqual(result.status, UNPRIVATE_UNLESS_TOR)
        self.assertEqual(result.url, "about:newtab")


class TestSocketGuard(unittest.TestCase):
    def test_null_tor_connect_records_and_refuses(self):
        tor = null_tor()
        with self.assertRaises(Exception):
            tor.connect("example.onion", 80)
        self.assertEqual(tor.connects, [("example.onion", 80)])
        self.assertIs(socket.AF_INET, socket.AF_INET)


if __name__ == "__main__":
    unittest.main()
