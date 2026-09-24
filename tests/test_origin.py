"""Pinned origin bytes, bundle hash, and vort1 mint round-trip."""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from rx.fence import DISPLAY_NAME, EXAMPLE_ORIGIN, PROGRAM_ID, UNPRIVATE_UNLESS_TOR
from rx.origin import (
    BROWSER_HTML,
    ORIGIN_FILE,
    mint_vortice_deploy_key,
    parse_vortice_key,
    read_origin_text,
    verify_vortice_download,
    vortice_bundle_hash,
)
from rx.pack import pack_bytes

ROOT = Path(__file__).resolve().parent.parent

# sha256 bundle for EXAMPLE_ORIGIN + the committed origin bytes.
# Recompute with: python -m rx.mint --origin <EXAMPLE_ORIGIN>
GOLDEN_EXAMPLE_BUNDLE = "1fc98c56c26b553e1c94d3a46feb08d8888f28473085640ab17fa82275f506cc"


class TestOrigin(unittest.TestCase):
    def test_pack_matches_committed_bytes(self):
        html, body = pack_bytes()
        self.assertEqual(BROWSER_HTML.read_bytes(), html)
        self.assertEqual(ORIGIN_FILE.read_bytes(), body)
        self.assertTrue(body.endswith(b"\n"))
        self.assertFalse(body.startswith(b"\xef\xbb\xbf"))

    def test_body_contract(self):
        source = read_origin_text()
        doc = json.loads(source)
        self.assertEqual(doc["programId"], PROGRAM_ID)
        self.assertEqual(doc["name"], DISPLAY_NAME)
        self.assertIs(doc["galleryReady"], False)
        self.assertIs(doc["vpnRelay"], False)
        self.assertEqual(doc["relay"], "tor")
        self.assertEqual(doc["statusUnprivate"], UNPRIVATE_UNLESS_TOR)
        self.assertIn(UNPRIVATE_UNLESS_TOR, doc["browser.html"])
        self.assertIn("decideNavigation", doc["browser.html"])
        self.assertNotIn("enableVpn", doc["browser.html"])
        self.assertNotIn("chrome.proxy", doc["browser.html"])
        self.assertIn("VPN_PROXY_PORT = 1080", doc["browser.html"])
        self.assertEqual(doc["browser.html"], BROWSER_HTML.read_text(encoding="utf-8"))

    def test_hash_changes_when_bytes_change(self):
        source = read_origin_text()
        base = vortice_bundle_hash(
            program_id=PROGRAM_ID,
            name=DISPLAY_NAME,
            origin=EXAMPLE_ORIGIN,
            source=source,
        )
        flipped = vortice_bundle_hash(
            program_id=PROGRAM_ID,
            name=DISPLAY_NAME,
            origin=EXAMPLE_ORIGIN,
            source=source + " ",
        )
        self.assertNotEqual(base, flipped)
        self.assertEqual(len(base), 64)

    def test_golden_bundle(self):
        source = read_origin_text()
        got = vortice_bundle_hash(
            program_id=PROGRAM_ID,
            name=DISPLAY_NAME,
            origin=EXAMPLE_ORIGIN,
            source=source,
        )
        self.assertEqual(got, GOLDEN_EXAMPLE_BUNDLE)

    def test_mint_roundtrip_and_reserved_id(self):
        source = read_origin_text()
        nonce = "ab" * 16
        key = mint_vortice_deploy_key(
            program_id=PROGRAM_ID,
            name=DISPLAY_NAME,
            origin=EXAMPLE_ORIGIN,
            source=source,
            nonce=nonce,
        )
        self.assertIsNotNone(key)
        self.assertTrue(key.startswith("vort1."))
        parsed = parse_vortice_key(key)
        self.assertEqual(parsed["id"], PROGRAM_ID)
        self.assertEqual(parsed["name"], DISPLAY_NAME)
        self.assertEqual(parsed["origin"], EXAMPLE_ORIGIN)
        verified = verify_vortice_download(key, source)
        self.assertIsNotNone(verified)
        self.assertIsNone(verify_vortice_download(key, source + "x"))
        self.assertIsNone(
            mint_vortice_deploy_key(
                program_id="shear-reserve-v1",
                name="nope",
                origin=EXAMPLE_ORIGIN,
                source=source,
                nonce=nonce,
            )
        )

    def test_node_json_mac_matches(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        source = read_origin_text()
        nonce = "cd" * 16
        spec = {
            "programId": PROGRAM_ID,
            "name": DISPLAY_NAME,
            "origin": EXAMPLE_ORIGIN,
            "sourcePath": str(ORIGIN_FILE),
            "n": nonce,
        }
        spec_path = ROOT / "tests" / ".mint-spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        try:
            proc = subprocess.run(
                [node, str(ROOT / "tests" / "mint_crosscheck.js"), str(spec_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        finally:
            spec_path.unlink(missing_ok=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        got = json.loads(proc.stdout)
        key = mint_vortice_deploy_key(
            program_id=PROGRAM_ID,
            name=DISPLAY_NAME,
            origin=EXAMPLE_ORIGIN,
            source=source,
            nonce=nonce,
        )
        self.assertEqual(key, got["key"])
        self.assertEqual(
            vortice_bundle_hash(
                program_id=PROGRAM_ID,
                name=DISPLAY_NAME,
                origin=EXAMPLE_ORIGIN,
                source=source,
            ),
            got["bundle"],
        )


class TestJsGate(unittest.TestCase):
    def test_node_gate(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        proc = subprocess.run(
            [node, str(ROOT / "continuum" / "ui" / "gate.test.js")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
