#!/usr/bin/env python3
"""
Rx Privacy Browser — launch entry point.

Usage:
  python launch_rx.py              # Tor bridge + browser UI (loopback)
  python launch_rx.py --smoke      # identity + fail-closed status, no GUI
  python launch_rx.py --tk         # Tk shell, still fail-closed without Tor
  python launch_rx.py --gui-brief  # brief window if a display is available
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path when launched as a script
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rx.shell import RxShell, create_shell


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rx Privacy Browser")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Bootstrap shell, print Rx identity, exit (for CI / verification)",
    )
    parser.add_argument(
        "--gui-brief",
        action="store_true",
        help="Open a short-lived window for launch verification",
    )
    parser.add_argument(
        "--tk",
        action="store_true",
        help="Open the Tk shell instead of the Continuum browser bridge",
    )
    parser.add_argument("--port", type=int, default=8844)
    parser.add_argument(
        "--json",
        action="store_true",
        help="With --smoke, also print snapshot JSON",
    )
    args = parser.parse_args(argv)

    shell = create_shell(_ROOT)

    if args.smoke:
        text = shell.smoke_report()
        print(text)
        if args.json:
            import json

            print(json.dumps(shell.snapshot(), indent=2))
        # Gate: product identity must appear
        if "Rx" not in text:
            print("error: product identity Rx missing from smoke output", file=sys.stderr)
            return 1
        if "unprivate unless tor" not in text:
            print("error: fail-closed status missing from smoke output", file=sys.stderr)
            return 1
        if "vpn_relay=false" not in text:
            print("error: vpn relay fence missing from smoke output", file=sys.stderr)
            return 1
        return 0

    if args.gui_brief:
        from rx.ui_tk import try_run_gui_brief

        print(try_run_gui_brief(timeout_s=1.5))
        return 0

    if args.tk:
        print(shell.privacy.banner_line())
        print(f"status={shell.session.status_line()}")
        try:
            from rx.ui_tk import run_gui

            run_gui(shell)
        except Exception as exc:
            print(f"GUI launch failed ({exc}); smoke bootstrap follows:", file=sys.stderr)
            print(shell.smoke_report())
            return 0
        return 0

    from rx.bridge import main as bridge_main

    bridge_argv = ["--port", str(args.port)]
    return bridge_main(bridge_argv)


if __name__ == "__main__":
    raise SystemExit(main())
