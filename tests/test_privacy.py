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
        self.assertEqual(p.normalize_url("example.com"), "https://example.com")
        self.assertEqual(p.normalize_url("about:newtab"), "about:newtab")
        self.assertTrue(p.normalize_url("privacy search").startswith("about:search?"))

    def test_shell_bootstrap_applies_privacy(self):
        shell = RxShell(repo_root=ROOT)
        state = shell.bootstrap()
        self.assertTrue(state.started)
        self.assertFalse(shell.privacy.telemetry_enabled)
        self.assertEqual(shell.tabs.active_tab.url, "about:newtab")
        self.assertIsNotNone(state.bundled_vpn)
        self.assertEqual(state.bundled_vpn.version, "3.3.3")
        report = shell.smoke_report()
        self.assertIn("Rx", report)
        self.assertIn("smoke_ok", report)


if __name__ == "__main__":
    unittest.main()
