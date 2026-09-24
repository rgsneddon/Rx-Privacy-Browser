"""Mint a local vort1. deploy key. Does not contact a Shear node and does not mint SHE."""

from __future__ import annotations

import argparse
import sys

from rx.fence import DISPLAY_NAME, EXAMPLE_ORIGIN, PROGRAM_ID
from rx.origin import (
    mint_vortice_deploy_key,
    parse_vortice_key,
    read_origin_text,
    verify_vortice_download,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mint a vort1 deploy key for Rx Privacy Browser")
    parser.add_argument(
        "--origin",
        required=True,
        help=f"Exact origin URL that will serve the pinned bytes (example {EXAMPLE_ORIGIN})",
    )
    parser.add_argument("--program-id", default=PROGRAM_ID)
    parser.add_argument("--name", default=DISPLAY_NAME)
    parser.add_argument("--nonce", default=None, help="32 hex chars; omit for a random nonce")
    args = parser.parse_args(argv)
    source = read_origin_text()
    key = mint_vortice_deploy_key(
        program_id=args.program_id,
        name=args.name,
        origin=args.origin,
        source=source,
        nonce=args.nonce,
    )
    if not key:
        print("mint failed: check program id, origin, and nonce", file=sys.stderr)
        return 1
    parsed = parse_vortice_key(key)
    verified = verify_vortice_download(key, source)
    if not parsed or not verified:
        print("mint failed local verify", file=sys.stderr)
        return 1
    print(f"programId={parsed['id']}")
    print(f"name={parsed['name']}")
    print(f"origin={parsed['origin']}")
    print(f"bundle={parsed['bundle']}")
    print(f"bytes={len(source.encode('utf-8'))}")
    print("vpnRelay=false")
    print("relay=tor")
    print("galleryReady=false")
    print("NOT Ready for vortices.shear.digital")
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
