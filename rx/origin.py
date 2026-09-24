"""Pinned Continuum origin body: exact bytes, bundle hash, local vort1 mint."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from rx.fence import (
    DISPLAY_NAME,
    EXAMPLE_ORIGIN,
    ORIGIN_URL_PATH,
    PROGRAM_ID,
    VORTICE_KEY_PREFIX,
    VORTEX_PERSONAL,
)

ROOT = Path(__file__).resolve().parent.parent
ORIGIN_FILE = ROOT / "continuum" / "rx-privacy-browser.vortice.json"
BROWSER_HTML = ROOT / "continuum" / "browser.html"


def read_origin_text(path: Path | None = None) -> str:
    data = (path or ORIGIN_FILE).read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("origin body must not carry a BOM")
    return data.decode("utf-8")


def vortice_bundle_hash(*, program_id: str, name: str, origin: str, source: str) -> str:
    digest = hashlib.sha256()
    digest.update(VORTEX_PERSONAL.encode("utf-8"))
    digest.update(str(program_id).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(name).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(origin).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(source).encode("utf-8"))
    return digest.hexdigest()


def _canonical_body(*, id: str, name: str, origin: str, bundle: str, n: str | None) -> str:
    body: dict[str, object] = {
        "v": 1,
        "id": id,
        "name": name,
        "origin": origin,
        "bundle": bundle,
    }
    if n:
        body["n"] = n
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def mac_of(body: str) -> str:
    return hashlib.sha256(VORTEX_PERSONAL.encode("utf-8") + body.encode("utf-8")).hexdigest()[:40]


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode(text + pad)


def valid_program_id(program_id: str) -> str | None:
    import re

    ident = (program_id or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,64}", ident):
        return None
    if ident in {
        "shear-reserve-v1",
        "shear-join-v1",
        "shear-join-watch-v1",
        "pool-unlock-2044",
    }:
        return None
    return ident


def valid_origin(origin: str) -> str | None:
    from urllib.parse import urlparse

    raw = (origin or "").strip()
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return raw


def mint_vortice_deploy_key(
    *,
    program_id: str = PROGRAM_ID,
    name: str = DISPLAY_NAME,
    origin: str,
    source: str,
    nonce: str | None = None,
) -> str | None:
    import secrets

    ident = valid_program_id(program_id)
    url = valid_origin(origin)
    if not ident or not url or source is None:
        return None
    label = (name or ident).strip()
    if not label or len(label) > 64:
        return None
    n = nonce or secrets.token_hex(16)
    if len(n) != 32 or any(c not in "0123456789abcdefABCDEF" for c in n):
        return None
    n = n.lower()
    bundle = vortice_bundle_hash(program_id=ident, name=label, origin=url, source=source)
    body = _canonical_body(id=ident, name=label, origin=url, bundle=bundle, n=n)
    payload = {
        "v": 1,
        "id": ident,
        "name": label,
        "origin": url,
        "bundle": bundle,
        "n": n,
        "mac": mac_of(body),
    }
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return VORTICE_KEY_PREFIX + _b64url(encoded.encode("utf-8"))


def parse_vortice_key(key: str) -> dict | None:
    raw = (key or "").strip()
    if not raw.startswith(VORTICE_KEY_PREFIX):
        return None
    try:
        payload = json.loads(_b64url_decode(raw[len(VORTICE_KEY_PREFIX) :]).decode("utf-8"))
    except (ValueError, UnicodeError):
        return None
    if not isinstance(payload, dict):
        return None
    ident = valid_program_id(str(payload.get("id") or ""))
    origin = valid_origin(str(payload.get("origin") or ""))
    name = str(payload.get("name") or "")
    bundle = str(payload.get("bundle") or "")
    mac = str(payload.get("mac") or "").lower()
    n = str(payload.get("n") or "")
    if n and (len(n) != 32 or any(c not in "0123456789abcdef" for c in n.lower())):
        return None
    if not ident or not origin or not bundle or not name or len(name) > 64:
        return None
    body = _canonical_body(id=ident, name=name, origin=origin, bundle=bundle, n=n or None)
    if mac_of(body) != mac:
        return None
    return {
        "id": ident,
        "name": name,
        "origin": origin,
        "bundle": bundle,
        "n": n,
        "key": raw,
    }


def verify_vortice_download(key: str, source: str) -> dict | None:
    parsed = parse_vortice_key(key)
    if not parsed or source is None:
        return None
    bundle = vortice_bundle_hash(
        program_id=parsed["id"],
        name=parsed["name"],
        origin=parsed["origin"],
        source=source,
    )
    if bundle != parsed["bundle"]:
        return None
    return {**parsed, "source": source}


__all__ = [
    "BROWSER_HTML",
    "EXAMPLE_ORIGIN",
    "ORIGIN_FILE",
    "ORIGIN_URL_PATH",
    "mint_vortice_deploy_key",
    "parse_vortice_key",
    "read_origin_text",
    "verify_vortice_download",
    "vortice_bundle_hash",
]
