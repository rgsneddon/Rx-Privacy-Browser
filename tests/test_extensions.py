"""Unit tests driving real shipped rx.extensions.ExtensionRegistry."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rx.extensions import (  # noqa: E402
    ExtensionRegistry,
    REQUIRED_VPN_VERSION,
    BUNDLED_VPN_REL,
)


class TestExtensionRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = ExtensionRegistry(ROOT)

    def test_extensions_permitted_by_default(self):
        self.assertTrue(self.reg.extensions_permitted)

    def test_bundled_vpn_path_exists(self):
        path = self.reg.bundled_vpn_path()
        self.assertTrue(path.is_dir(), f"missing {path}")
        self.assertTrue((path / "manifest.json").is_file())

    def test_required_files_present(self):
        missing = self.reg.required_extension_files_present()
        self.assertEqual(missing, [], f"missing files: {missing}")

    def test_version_pin_3_3_3(self):
        pin = self.reg.read_vpn_version_pin()
        self.assertEqual(pin, REQUIRED_VPN_VERSION)
        self.assertEqual(REQUIRED_VPN_VERSION, "3.3.3")

    def test_load_bundled_vpn(self):
        info = self.reg.load_bundled_vpn()
        self.assertEqual(info.version, "3.3.3")
        self.assertTrue(info.enabled)
        self.assertIn("Restore Privacy", info.name)
        self.assertTrue(info.path.is_dir())
        # Real VPN entry points, not stubs
        bg = (info.path / "background.js").read_text(encoding="utf-8")
        self.assertIn("RptBrowserVpnCore", bg)
        core = (info.path / "lib" / "vpn_core.js").read_text(encoding="utf-8")
        self.assertIn("enableVpn", core)
        self.assertIn("browserScopeOnly", core)

    def test_resolve_and_enable_disable(self):
        path = self.reg.resolve_extension_path(str(BUNDLED_VPN_REL))
        self.assertTrue(path.is_dir())
        info = self.reg.load_unpacked(str(BUNDLED_VPN_REL))
        self.reg.disable(info.id)
        self.assertFalse(self.reg.get(info.id).enabled)
        self.reg.enable(info.id)
        self.assertTrue(self.reg.get(info.id).enabled)

    def test_permit_gate(self):
        self.reg.extensions_permitted = False
        with self.assertRaises(PermissionError):
            self.reg.load_unpacked(str(BUNDLED_VPN_REL))


if __name__ == "__main__":
    unittest.main()
