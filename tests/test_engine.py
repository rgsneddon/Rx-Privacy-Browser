"""Isolated engine command line stays on Tor SOCKS and refuses the VPN port."""

from __future__ import annotations

import unittest
from pathlib import Path

from rx.engine import engine_command, firefox_user_js, launch_isolated_engine
from rx.fence import TorUnavailable, VpnRelayForbidden
from rx.tor import FlagTor


class TestEngine(unittest.TestCase):
    def test_chrome_proxy_is_tor_socks(self):
        profile = Path("/tmp/rx-engine-profile-test")
        cmd = engine_command(
            "/usr/bin/google-chrome",
            ui_url="http://127.0.0.1:8844/?engine=abc",
            socks_port=9070,
            user_data_dir=profile,
        )
        joined = " ".join(cmd)
        self.assertIn("--disable-extensions", joined)
        self.assertIn("--proxy-server=socks5://127.0.0.1:9070", joined)
        self.assertIn("NOTFOUND", joined)
        self.assertIn("--force-webrtc-ip-handling-policy=disable_non_proxied_udp", joined)
        self.assertNotIn("1080", joined)
        self.assertNotIn("shewall", joined.lower())
        marked = engine_command(
            "/usr/bin/google-chrome",
            ui_url="http://127.0.0.1:8844/?engine=abc",
            socks_port=9070,
            user_data_dir=profile,
            engine_mark="rxemark",
        )
        self.assertIn("--user-agent=RxPrivacyBrowser/0.2 (Tor; rxemark)", marked)

    def test_firefox_remote_dns(self):
        text = firefox_user_js(9070)
        self.assertIn('user_pref("network.proxy.socks_remote_dns", true);', text)
        self.assertIn('user_pref("network.proxy.socks_port", 9070);', text)
        self.assertIn('user_pref("toolkit.telemetry.enabled", false);', text)
        self.assertIn('user_pref("media.peerconnection.enabled", false);', text)
        self.assertNotIn("1080", text)
        profile = Path("/tmp/rx-firefox-profile-test")
        cmd = engine_command(
            "/usr/bin/firefox",
            ui_url="http://127.0.0.1:8844/?engine=abc",
            socks_port=9070,
            user_data_dir=profile,
        )
        self.assertIn("-no-remote", cmd)
        self.assertIn('socks_remote_dns", true', (profile / "user.js").read_text(encoding="utf-8"))

    def test_vpn_port_refused(self):
        with self.assertRaises(VpnRelayForbidden):
            engine_command(
                "/usr/bin/google-chrome",
                ui_url="http://127.0.0.1/",
                socks_port=1080,
                user_data_dir=Path("/tmp/rx-engine-profile-test"),
            )

    def test_launch_refuses_without_circuit(self):
        with self.assertRaises(TorUnavailable):
            launch_isolated_engine(
                ui_url="http://127.0.0.1:8844/",
                socks_port=9070,
                tor=FlagTor(False),
            )


if __name__ == "__main__":
    unittest.main()
