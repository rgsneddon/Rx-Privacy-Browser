"""Isolated browser engine launched only behind a Tor SOCKS proxy.

The engine is a separate process with its own profile. It does not load the
bundled VPN extension and it does not read shewall.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rx.fence import TorUnavailable, reject_vpn_proxy_port, routing_allowed
from rx.isolate import assert_isolated, state_dir


def firefox_user_js(socks_port: int) -> str:
    reject_vpn_proxy_port(socks_port)
    prefs = [
        'user_pref("network.proxy.type", 1);',
        'user_pref("network.proxy.socks", "127.0.0.1");',
        f'user_pref("network.proxy.socks_port", {int(socks_port)});',
        'user_pref("network.proxy.socks_version", 5);',
        'user_pref("network.proxy.socks_remote_dns", true);',
        'user_pref("network.proxy.no_proxies_on", "127.0.0.1, localhost");',
        'user_pref("network.dns.disablePrefetch", true);',
        'user_pref("network.prefetch-next", false);',
        'user_pref("media.peerconnection.enabled", false);',
        'user_pref("toolkit.telemetry.enabled", false);',
        'user_pref("toolkit.telemetry.unified", false);',
        'user_pref("datareporting.healthreport.uploadEnabled", false);',
        'user_pref("datareporting.policy.dataSubmissionEnabled", false);',
        'user_pref("browser.safebrowsing.downloads.remote.enabled", false);',
        'user_pref("privacy.donottrackheader.enabled", true);',
        'user_pref("privacy.trackingprotection.enabled", true);',
        'user_pref("privacy.trackingprotection.pbmode.enabled", true);',
        'user_pref("network.cookie.cookieBehavior", 1);',
        'user_pref("extensions.autoDisableScopes", 15);',
        'user_pref("extensions.enabledScopes", 0);',
        'user_pref("browser.shell.checkDefaultBrowser", false);',
    ]
    text = "\n".join(prefs) + "\n"
    if "1080" in text or "shewall" in text.lower():
        raise RuntimeError("firefox profile failed the relay fence")
    return text


def engine_command(
    binary: str,
    *,
    ui_url: str,
    socks_port: int,
    user_data_dir: Path,
) -> list[str]:
    reject_vpn_proxy_port(socks_port)
    profile = assert_isolated(user_data_dir)
    name = Path(binary).name.lower()
    if "firefox" in name:
        profile.mkdir(parents=True, exist_ok=True)
        (profile / "user.js").write_text(firefox_user_js(socks_port), encoding="utf-8")
        return [binary, "-profile", str(profile), "-no-remote", "-new-instance", ui_url]
    profile.mkdir(parents=True, exist_ok=True)
    return [
        binary,
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-client-side-phishing-detection",
        "--disable-component-update",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        f"--proxy-server=socks5://127.0.0.1:{int(socks_port)}",
        "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1",
        "--proxy-bypass-list=127.0.0.1;localhost",
        "--new-window",
        ui_url,
    ]


def find_engine() -> str | None:
    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "firefox",
    ):
        found = shutil.which(name)
        if found:
            return found
    return None


def launch_isolated_engine(*, ui_url: str, socks_port: int, tor=None) -> subprocess.Popen:
    if tor is not None and not routing_allowed(tor.state):
        raise TorUnavailable()
    reject_vpn_proxy_port(socks_port)
    binary = find_engine()
    if not binary:
        raise RuntimeError("no browser engine on PATH")
    profile = assert_isolated(state_dir() / "engine-profile")
    cmd = engine_command(binary, ui_url=ui_url, socks_port=socks_port, user_data_dir=profile)
    return subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
