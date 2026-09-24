"""URL policy: what may be typed, and what needs a Tor circuit.

Onion names are never treated as clearnet DNS names. Private and local
targets are refused. Tracker query parameters are stripped before any fetch.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

_ONION_ADDR = re.compile(r"^[a-z2-7]{16}$|^[a-z2-7]{56}$")
_ONION_LABEL = re.compile(r"^[a-z2-7]{1,63}$")
_CLEAR_HOST = re.compile(r"^[a-z0-9.-]{1,253}$")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)

TRACKER_SUFFIXES = (
    "doubleclick.net",
    "google-analytics.com",
    "googletagmanager.com",
    "facebook.net",
    "scorecardresearch.com",
    "hotjar.com",
)

TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "igshid",
    }
)


@dataclass(frozen=True)
class ClassifiedUrl:
    ok: bool
    url: str
    network: bool
    onion: bool
    reason: str = ""
    host: str = ""


def is_onion_host(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    if not host.endswith(".onion"):
        return False
    labels = host.split(".")
    if len(labels) < 2 or labels[-1] != "onion":
        return False
    if not _ONION_ADDR.fullmatch(labels[-2]):
        return False
    return all(_ONION_LABEL.fullmatch(lab) for lab in labels[:-1])


def is_tracker_host(host: str) -> bool:
    h = (host or "").lower().rstrip(".")
    for suf in TRACKER_SUFFIXES:
        if h == suf or h.endswith("." + suf):
            return True
    return False


def _private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _bad_host(host: str) -> str | None:
    h = (host or "").lower().rstrip(".")
    if not h:
        return "empty-host"
    if h in {"localhost", "localhost.localdomain"} or h.endswith(".localhost") or h.endswith(".local"):
        return "local-name"
    if _private_ip(h):
        return "private-ip"
    if h.endswith(".onion"):
        if is_onion_host(h):
            return None
        return "bad-onion"
    if ".." in h or not _CLEAR_HOST.fullmatch(h):
        return "bad-host"
    labels = h.split(".")
    if any(not lab or len(lab) > 63 or lab.startswith("-") or lab.endswith("-") for lab in labels):
        return "bad-host"
    return None


def _strip_tracking(query: str) -> str:
    pairs = [
        (k, v)
        for k, v in parse_qsl(query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    return urlencode(pairs)


def classify_url(raw: str, *, prefer_https: bool = True) -> ClassifiedUrl:
    s = (raw or "").strip()
    if not s:
        return ClassifiedUrl(True, "about:newtab", False, False, "empty", "")
    lower = s.lower()
    if lower.startswith("about:"):
        if lower in {"about:newtab", "about:blank"} or lower.startswith("about:search?"):
            url = "about:newtab" if lower == "about:blank" else s
            return ClassifiedUrl(True, url, False, False, "local", "")
        return ClassifiedUrl(False, "", False, False, "about-blocked", "")
    if _SCHEME.match(lower) and not lower.startswith(("http://", "https://")):
        return ClassifiedUrl(False, "", False, False, "scheme", "")
    if "://" not in s:
        if " " in s or "." not in s:
            return ClassifiedUrl(
                True,
                f"about:search?q={quote_plus(s)}",
                False,
                False,
                "local-search",
                "",
            )
        hostpart = s.split("/")[0].split("@")[-1]
        hostonly = hostpart.split(":")[0]
        if is_onion_host(hostonly):
            s = "http://" + s
        elif prefer_https:
            s = "https://" + s
        else:
            s = "http://" + s
    parts = urlsplit(s)
    scheme = (parts.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return ClassifiedUrl(False, "", False, False, "scheme", "")
    if parts.username or parts.password:
        return ClassifiedUrl(False, "", False, False, "userinfo", "")
    try:
        port = parts.port
    except ValueError:
        return ClassifiedUrl(False, "", False, False, "port", "")
    if port is not None and (port < 1 or port > 65535):
        return ClassifiedUrl(False, "", False, False, "port", "")
    host = (parts.hostname or "").lower().rstrip(".")
    why = _bad_host(host)
    if why:
        return ClassifiedUrl(False, "", False, False, why, host)
    onion = is_onion_host(host)
    netloc = f"{host}:{port}" if port else host
    path = parts.path or "/"
    query = _strip_tracking(parts.query)
    url = urlunsplit((scheme, netloc, path, query, ""))
    return ClassifiedUrl(True, url, True, onion, "onion" if onion else "clearnet", host)


_MNEMONIC_WORD = re.compile(r"^[a-z]{3,8}$")
_SECRET_HEX = re.compile(r"^[0-9a-fA-F]{64}$|^[0-9a-fA-F]{128}$")
_XPRV = re.compile(r"(?:^|\s)xprv[1-9a-z]{10,}")


def secret_paste_reason(raw: str) -> str | None:
    """Why a paste must not enter Rx, or None when it is ordinary navigation.

    The returned reason never includes the pasted text.
    """
    text = (raw or "").strip()
    if not text:
        return None
    low = text.lower()
    if "shewall" in low:
        return "shewall"
    if (
        "begin private key" in low
        or "begin openssh private key" in low
        or "begin ec private key" in low
    ):
        return "private-key"
    if _XPRV.search(low):
        return "private-key"
    if _SECRET_HEX.fullmatch(text):
        return "private-key"
    words = low.split()
    if len(words) in {12, 15, 18, 21, 24} and all(_MNEMONIC_WORD.fullmatch(w) for w in words):
        return "mnemonic"
    return None
