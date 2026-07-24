#!/usr/bin/env python3
"""
Rx Privacy Browser — launch entry point.

Usage:
  python launch_rx.py           # full GUI shell
  python launch_rx.py --smoke   # bootstrap + print identity (no blocking GUI)
  python launch_rx.py --gui-brief  # brief GUI smoke if display available
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
        return 0

    if args.gui_brief:
        from rx.ui_tk import try_run_gui_brief

        print(try_run_gui_brief(timeout_s=1.5))
        return 0

    # Full interactive shell
    print(shell.privacy.banner_line())
    print(f"window_title={shell.privacy.window_title()}")
    try:
        from rx.ui_tk import run_gui

        run_gui(shell)
    except Exception as exc:
        # Honest fallback: bootstrap still proves shell identity
        print(f"GUI launch failed ({exc}); smoke bootstrap follows:", file=sys.stderr)
        print(shell.smoke_report())
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
