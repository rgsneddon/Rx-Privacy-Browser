"""Unit tests driving real shipped rx.extensions.ExtensionRegistry."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rx.extensions import (  # noqa: E402
    ExtensionRegistry,
    ON_DISK_VPN_CATALOG_VERSION,
    BUNDLED_VPN_REL,
)
from rx.fence import VpnRelayForbidden  # noqa: E402


class TestExtensionRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = ExtensionRegistry(ROOT)

    def test_extensions_not_permitted_on_tor_path(self):
        self.assertFalse(self.reg.extensions_permitted)

    def test_bundled_vpn_path_exists(self):
        path = self.reg.bundled_vpn_path()
        self.assertTrue(path.is_dir(), f"missing {path}")
        self.assertTrue((path / "manifest.json").is_file())

    def test_required_files_present(self):
        missing = self.reg.required_extension_files_present()
        self.assertEqual(missing, [], f"missing files: {missing}")

    def test_on_disk_catalog_version_is_not_a_bootstrap_pin(self):
        pin = self.reg.read_vpn_version_pin()
        self.assertEqual(pin, ON_DISK_VPN_CATALOG_VERSION)
        self.assertEqual(ON_DISK_VPN_CATALOG_VERSION, "3.3.3")
        self.assertEqual(self.reg.list_loaded(), [])

    def test_load_bundled_vpn_is_refused(self):
        with self.assertRaises(VpnRelayForbidden) as caught:
            self.reg.load_bundled_vpn()
        self.assertEqual(str(caught.exception), "unprivate unless tor")
        self.assertEqual(self.reg.list_loaded(), [])

    def test_permitting_extensions_still_refuses_vpn_package(self):
        self.reg.extensions_permitted = True
        with self.assertRaises(VpnRelayForbidden):
            self.reg.load_unpacked(str(BUNDLED_VPN_REL))
        self.assertEqual(self.reg.list_loaded(), [])

    def test_permit_gate(self):
        self.reg.extensions_permitted = False
        with self.assertRaises(PermissionError):
            self.reg.load_unpacked(str(BUNDLED_VPN_REL))


if __name__ == "__main__":
    unittest.main()
