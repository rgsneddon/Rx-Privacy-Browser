"""Loopback bridge: exact origin bytes, fail-closed navigate, no VPN launch."""

from __future__ import annotations

import json
import unittest
from urllib.request import Request, urlopen

from rx.fence import PRIVATE_VIA_TOR, UNPRIVATE_UNLESS_TOR
from rx.fetch import Page
from rx.origin import ORIGIN_FILE, ORIGIN_URL_PATH
from rx.session import BrowseSession
from rx.tor import FlagTor, null_tor
from rx.bridge import start_bridge

ONION = "http://" + ("f" * 56) + ".onion/"


class TestBridge(unittest.TestCase):
    def setUp(self):
        self.servers = []

    def tearDown(self):
        for httpd in self.servers:
            httpd.shutdown()
            httpd.server_close()

    def _start(self, session, launcher=None):
        httpd = start_bridge(session, port=0, launcher=launcher)
        self.servers.append(httpd)
        return httpd

    def _get(self, httpd, path):
        host, port = httpd.server_address[:2]
        with urlopen(f"http://{host}:{port}{path}", timeout=3) as res:
            return res.status, res.read()

    def _post(self, httpd, path, payload, token=""):
        host, port = httpd.server_address[:2]
        req = Request(
            f"http://{host}:{port}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Rx-Token": token},
            method="POST",
        )
        try:
            with urlopen(req, timeout=3) as res:
                return res.status, json.loads(res.read().decode())
        except Exception as exc:
            if hasattr(exc, "code") and hasattr(exc, "read"):
                return exc.code, json.loads(exc.read().decode())
            raise

    def test_status_and_origin_bytes(self):
        httpd = self._start(BrowseSession(null_tor()))
        code, raw = self._get(httpd, "/rx/status")
        self.assertEqual(code, 200)
        status = json.loads(raw)
        self.assertEqual(status["status"], UNPRIVATE_UNLESS_TOR)
        self.assertFalse(status["private"])
        self.assertFalse(status["vpnRelay"])
        code, body = self._get(httpd, ORIGIN_URL_PATH)
        self.assertEqual(code, 200)
        self.assertEqual(body, ORIGIN_FILE.read_bytes())
        code, page = self._get(httpd, "/")
        text = page.decode()
        self.assertIn(UNPRIVATE_UNLESS_TOR, text)
        self.assertIn(httpd.token, text)
        self.assertNotIn('"engineProxied":true', text)

    def test_navigate_blocked_without_fetch(self):
        tor = null_tor()
        called = []
        session = BrowseSession(tor, fetcher=lambda *a, **k: called.append(a))
        httpd = self._start(session)
        code, payload = self._post(httpd, "/rx/navigate", {"url": ONION}, token=httpd.token)
        self.assertEqual(code, 403)
        self.assertEqual(payload["status"], UNPRIVATE_UNLESS_TOR)
        self.assertTrue(payload["blocked"])
        self.assertFalse(payload["fetch"])
        self.assertFalse(payload["vpnRelay"])
        self.assertEqual(called, [])
        self.assertEqual(tor.connects, [])

    def test_missing_token_does_not_fetch(self):
        called = []
        session = BrowseSession(FlagTor(True), fetcher=lambda *a, **k: called.append(a))
        httpd = self._start(session)
        code, payload = self._post(httpd, "/rx/navigate", {"url": ONION}, token="")
        self.assertEqual(code, 403)
        self.assertEqual(payload["status"], UNPRIVATE_UNLESS_TOR)
        self.assertEqual(called, [])

    def test_navigate_when_routing(self):
        seen = []

        def fetcher(url, _tor):
            seen.append(url)
            return Page(
                url=url,
                http_status=200,
                title="Hi",
                text="page text",
                content_type="text/html",
                tls_verified=False,
                onion=True,
            )

        httpd = self._start(BrowseSession(FlagTor(True), fetcher=fetcher))
        code, payload = self._post(httpd, "/rx/navigate", {"url": ONION}, token=httpd.token)
        self.assertEqual(code, 200)
        self.assertEqual(payload["status"], PRIVATE_VIA_TOR)
        self.assertTrue(payload["private"])
        self.assertTrue(payload["fetch"])
        self.assertFalse(payload["vpnRelay"])
        self.assertEqual(payload["text"], "page text")
        self.assertEqual(seen, [payload["url"]])

    def test_engine_not_launched_when_tor_down(self):
        launched = []
        httpd = self._start(BrowseSession(null_tor()), launcher=lambda *a: launched.append(a))
        code, payload = self._post(httpd, "/rx/engine", {}, token=httpd.token)
        self.assertEqual(code, 403)
        self.assertEqual(payload["status"], UNPRIVATE_UNLESS_TOR)
        self.assertFalse(payload["launched"])
        self.assertEqual(launched, [])
        self.assertEqual(httpd.launch_count, 0)

    def test_engine_launches_only_when_routing(self):
        launched = []
        httpd = self._start(BrowseSession(FlagTor(True)), launcher=lambda *a: launched.append(a))
        code, payload = self._post(httpd, "/rx/engine", {}, token=httpd.token)
        self.assertEqual(code, 200)
        self.assertEqual(payload["status"], PRIVATE_VIA_TOR)
        self.assertTrue(payload["launched"])
        self.assertEqual(len(launched), 1)
        ui, socks_port = launched[0]
        self.assertIn("engine=", ui)
        self.assertNotEqual(socks_port, 1080)
        self.assertEqual(httpd.launch_count, 1)


if __name__ == "__main__":
    unittest.main()
