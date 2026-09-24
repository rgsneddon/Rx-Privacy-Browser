"""Ready fences: no VPN bootstrap require, onion stays on Tor SOCKS."""

from __future__ import annotations

import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from rx.fence import UNPRIVATE_UNLESS_TOR, VpnRelayForbidden
from rx.shell import RxShell
from rx.tor_socks import socks5_connect

ROOT = Path(__file__).resolve().parent.parent
ONION = "c" * 56 + ".onion"


class TestVpnNotRequired(unittest.TestCase):
    def test_bootstrap_without_extension_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            shell = RxShell(repo_root=Path(tmp))

            def boom(*_a, **_k):
                raise AssertionError("bootstrap touched the vpn package")

            shell.extensions.load_bundled_vpn = boom
            shell.extensions.required_extension_files_present = boom
            shell.extensions.read_vpn_version_pin = boom
            state = shell.bootstrap()
        self.assertTrue(state.started)
        self.assertIsNone(state.bundled_vpn)
        self.assertFalse(state.vpn_relay)
        self.assertFalse(shell.extensions.extensions_permitted)
        self.assertEqual(shell.extensions.list_loaded(), [])
        self.assertEqual(shell.session.status_line(), UNPRIVATE_UNLESS_TOR)

    def test_shell_and_tk_do_not_load_the_extension(self):
        shell_src = (ROOT / "rx" / "shell.py").read_text(encoding="utf-8")
        ui_src = (ROOT / "rx" / "ui_tk.py").read_text(encoding="utf-8")
        for src in (shell_src, ui_src):
            self.assertNotIn("load_bundled_vpn", src)
            self.assertNotIn("required_extension_files_present", src)
            self.assertNotIn("3.3.3", src)
            self.assertNotIn("extensions must be permitted", src)
        shell = RxShell(repo_root=ROOT)
        shell.bootstrap()
        with self.assertRaises(VpnRelayForbidden):
            shell.enable_extension("restore-privacy-vpn")
        self.assertEqual(shell.extensions.list_loaded(), [])

    def test_host_bridge_is_status_and_tor_only(self):
        banned = (
            "sendrawtransaction",
            "jsonrpc",
            "peer rpc",
            "invent",
            "pool-unlock",
            "shewall.bin",
        )
        for name in ("bridge.py", "session.py", "fetch.py", "shell.py", "ui_tk.py"):
            text = (ROOT / "rx" / name).read_text(encoding="utf-8").lower()
            for needle in banned:
                self.assertNotIn(needle, text, name)


class TestOnionSocksOnly(unittest.TestCase):
    def test_typed_onion_uses_socks_hostname_not_dns(self):
        left, right = socket.socketpair()
        left.settimeout(2)
        right.settimeout(2)
        seen = {}

        def peer():
            self.assertEqual(right.recv(3), b"\x05\x01\x00")
            right.sendall(b"\x05\x00")
            buf = b""
            while len(buf) < 5:
                buf += right.recv(256)
            ln = buf[4]
            while len(buf) < 5 + ln + 2:
                buf += right.recv(256)
            seen["req"] = buf
            right.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")

        thread = threading.Thread(target=peer)
        thread.start()

        def explode(*_a, **_k):
            raise AssertionError("clearnet dns")

        with patch("socket.getaddrinfo", explode):
            socks5_connect(left, ONION, 80)
        thread.join(2)
        req = seen["req"]
        self.assertEqual(req[3], 3)
        self.assertEqual(req[5 : 5 + req[4]].decode(), ONION)
        left.close()
        right.close()

    def test_tor_down_onion_does_not_resolve(self):
        shell = RxShell(repo_root=ROOT)
        shell.bootstrap()

        def explode(*_a, **_k):
            raise AssertionError("clearnet dns or socket")

        with patch("socket.getaddrinfo", explode), patch("socket.socket", explode):
            result = shell.navigate("http://" + ONION + "/hidden")
        self.assertEqual(result.status, UNPRIVATE_UNLESS_TOR)
        self.assertTrue(result.blocked)
        self.assertFalse(result.fetch)
        self.assertTrue(result.onion)
        self.assertEqual(shell.tabs.active_tab.url, "about:newtab")


if __name__ == "__main__":
    unittest.main()
