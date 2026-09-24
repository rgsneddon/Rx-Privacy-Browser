"""Unit tests driving real shipped rx.privacy.PrivacyDefaults."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rx.privacy import PrivacyDefaults, default_privacy  # noqa: E402
from rx.shell import RxShell  # noqa: E402


class TestPrivacyDefaults(unittest.TestCase):
    def test_no_telemetry_default(self):
        p = default_privacy()
        self.assertFalse(p.telemetry_enabled)
        self.assertEqual(list(p.analytics_endpoints), [])
        p.assert_no_telemetry()

    def test_private_start(self):
        p = default_privacy()
        self.assertTrue(p.start_private)
        self.assertEqual(p.start_url, "about:newtab")
        self.assertTrue(p.tracker_blocking)
        self.assertTrue(p.send_do_not_track)

    def test_product_identity_rx(self):
        p = default_privacy()
        self.assertEqual(p.product_name, "Rx")
        title = p.window_title()
        self.assertIn("Rx", title)
        self.assertIn("Restore Privacy", title)
        self.assertIn("Rx", p.banner_line())

    def test_normalize_url_https_preference(self):
        p = default_privacy()
        self.assertEqual(p.normalize_url("example.com"), "https://example.com/")
        self.assertEqual(p.normalize_url("about:newtab"), "about:newtab")
        self.assertTrue(p.normalize_url("privacy search").startswith("about:search?"))
        onion = "a" * 56 + ".onion"
        self.assertEqual(p.normalize_url(onion), "http://" + onion + "/")
        self.assertEqual(p.normalize_url("javascript:alert(1)"), "about:newtab")

    def test_shell_bootstrap_applies_privacy(self):
        shell = RxShell(repo_root=ROOT)
        state = shell.bootstrap()
        self.assertTrue(state.started)
        self.assertFalse(shell.privacy.telemetry_enabled)
        self.assertFalse(shell.privacy.vpn_relay)
        self.assertEqual(shell.privacy.traffic_relay, "tor")
        self.assertEqual(shell.privacy.status_unprivate, "unprivate unless tor")
        self.assertEqual(shell.session.status_line(), "unprivate unless tor")
        self.assertIsNone(state.bundled_vpn)
        self.assertEqual(shell.tabs.active_tab.url, "about:newtab")
        report = shell.smoke_report()
        self.assertIn("Rx", report)
        self.assertIn("smoke_ok", report)
        self.assertIn("unprivate unless tor", report)
        self.assertIn("vpn_relay=false", report)

    def test_shell_blocks_onion_without_tor(self):
        shell = RxShell(repo_root=ROOT)
        shell.bootstrap()
        result = shell.navigate("http://" + ("b" * 56) + ".onion/path")
        self.assertTrue(result.blocked)
        self.assertFalse(result.fetch)
        self.assertFalse(result.private)
        self.assertEqual(result.status, "unprivate unless tor")
        self.assertEqual(shell.tabs.active_tab.url, "about:newtab")


if __name__ == "__main__":
    unittest.main()
