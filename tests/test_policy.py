"""URL policy vectors shared with the browser gate."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rx.policy import classify_url

ROOT = Path(__file__).resolve().parent.parent
VECTORS = ROOT / "tests" / "url_vectors.json"


class TestPolicyVectors(unittest.TestCase):
    def test_vectors_match(self):
        rows = json.loads(VECTORS.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 8)
        for row in rows:
            got = classify_url(row["in"])
            self.assertEqual(got.ok, row["ok"], row["in"])
            self.assertEqual(got.network, row["network"], row["in"])
            self.assertEqual(got.onion, row["onion"], row["in"])
            self.assertEqual(got.url, row["url"], row)
            self.assertEqual(got.reason, row["reason"], row["in"])

    def test_tracker_host_not_fetched_shape(self):
        got = classify_url("https://www.google-analytics.com/collect")
        self.assertTrue(got.ok)
        self.assertEqual(got.host, "www.google-analytics.com")


if __name__ == "__main__":
    unittest.main()
