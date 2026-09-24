"""Unit tests driving real shipped rx.tabs.TabManager."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rx.tabs import TabManager  # noqa: E402


class TestTabManager(unittest.TestCase):
    def test_starts_with_one_tab(self):
        tm = TabManager(start_url="about:newtab")
        self.assertEqual(tm.tab_count(), 1)
        self.assertIsNotNone(tm.active_tab)
        self.assertEqual(tm.active_tab.url, "about:newtab")

    def test_open_switch_close(self):
        tm = TabManager(start_url="about:newtab")
        first_id = tm.active_id
        t2 = tm.open_tab(url="https://example.com", title="Example")
        self.assertEqual(tm.tab_count(), 2)
        self.assertEqual(tm.active_id, t2.id)
        tm.switch_tab(first_id)
        self.assertEqual(tm.active_id, first_id)
        tm.close_tab(first_id)
        self.assertEqual(tm.tab_count(), 1)
        self.assertEqual(tm.active_id, t2.id)

    def test_close_last_opens_replacement(self):
        tm = TabManager()
        only = tm.active_id
        tm.close_tab(only)
        self.assertEqual(tm.tab_count(), 1)
        self.assertNotEqual(tm.active_id, only)

    def test_navigate_active(self):
        tm = TabManager(start_url="about:newtab")
        tm.navigate_active("https://restoreprivacy.online/")
        self.assertEqual(tm.active_tab.url, "https://restoreprivacy.online/")
        self.assertTrue(len(tm.active_tab.history) >= 1)

    def test_back_forward(self):
        tm = TabManager(start_url="about:newtab")
        tm.navigate_active("https://example.com/")
        tm.navigate_active("https://example.org/")
        tm.go_back()
        self.assertEqual(tm.active_tab.url, "https://example.com/")
        tm.go_forward()
        self.assertEqual(tm.active_tab.url, "https://example.org/")


if __name__ == "__main__":
    unittest.main()
