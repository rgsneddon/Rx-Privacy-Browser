"""Onion smoke: fetch one URL through Tor, or refuse without fetching."""

from __future__ import annotations

import argparse
import sys

from rx.fence import PRIVATE_VIA_TOR, UNPRIVATE_UNLESS_TOR
from rx.session import BrowseSession

# Well-known DuckDuckGo v3 onion. Override with --url. Not fetched unless a circuit is up.
DEFAULT_ONION = (
    "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/"
)


def smoke_once(session: BrowseSession, url: str, out=print) -> int:
    result = session.navigate(url)
    if not result.private or result.status != PRIVATE_VIA_TOR:
        out(UNPRIVATE_UNLESS_TOR)
        out("not_fetched")
        return 2
    if result.blocked or not result.fetch:
        out(result.status)
        out("not_fetched")
        out(result.reason or "blocked")
        return 1
    out(result.status)
    out(f"url={result.url}")
    out(f"http={result.http_status}")
    if result.title:
        out(f"title={result.title}")
    snippet = (result.text or "").strip().replace("\n", " ")[:180]
    if snippet:
        out(f"text={snippet}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from rx.tor import LiveTor

    parser = argparse.ArgumentParser(description="Fetch one URL through Tor or fail closed")
    parser.add_argument("--url", default=DEFAULT_ONION)
    parser.add_argument("--wait", type=float, default=20.0, help="Seconds to wait for a circuit")
    parser.add_argument("--no-spawn", action="store_true")
    args = parser.parse_args(argv)
    tor = LiveTor()
    if not args.no_spawn:
        tor.ensure()
    else:
        tor.refresh()
    import time

    deadline = time.monotonic() + max(0.0, args.wait)
    while time.monotonic() < deadline:
        tor.refresh()
        from rx.fence import routing_allowed

        if routing_allowed(tor.state):
            break
        time.sleep(0.5)
    session = BrowseSession(tor)
    try:
        return smoke_once(session, args.url)
    finally:
        tor.stop()


if __name__ == "__main__":
    raise SystemExit(main())
