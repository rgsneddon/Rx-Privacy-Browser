"""HTTP(S) fetch over a Tor SOCKS socket. No direct TCP and no local DNS."""

from __future__ import annotations

import http.client
import re
import ssl
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from rx.fence import USER_AGENT
from rx.policy import classify_url, is_onion_host, is_tracker_host

MAX_BODY = 2_000_000
MAX_REDIRECTS = 4


class PolicyStop(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Page:
    url: str
    http_status: int
    title: str
    text: str
    content_type: str
    tls_verified: bool
    onion: bool


class _BoundHTTP(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, sock, timeout: float) -> None:
        super().__init__(host, port, timeout=timeout)
        self.sock = sock

    def connect(self) -> None:
        if self.sock is None:
            raise RuntimeError("direct TCP is forbidden")


def tls_context_for(host: str) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if is_onion_host(host):
        # Onion certificates are not public-WebPKI. The circuit is still Tor.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _title(html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()[:200]


def html_to_text(html: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)\b.*?>.*?</\1>", " ", html or "")
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    for src, dst in (
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
    ):
        raw = raw.replace(src, dst)
    return re.sub(r"\s+", " ", raw).strip()[:20000]


def _decode(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type or "", re.I)
    if match:
        charset = match.group(1)
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _target_port(scheme: str, port: int | None) -> int:
    if port:
        return port
    return 443 if scheme == "https" else 80


def _exchange(sock, host: str, port: int, path: str, timeout: float) -> tuple[int, str, bytes, str]:
    conn = _BoundHTTP(host, port, sock, timeout)
    try:
        conn.request(
            "GET",
            path or "/",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "identity",
                "DNT": "1",
                "Connection": "close",
            },
        )
        resp = conn.getresponse()
        body = resp.read(MAX_BODY + 1)
        ctype = resp.getheader("Content-Type") or ""
        location = resp.getheader("Location") or ""
        status = resp.status
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if len(body) > MAX_BODY:
        body = body[:MAX_BODY]
    return status, ctype, body, location


def fetch_through_tor(url: str, tor, timeout: float = 45.0) -> Page:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        classified = classify_url(current)
        if not classified.ok or not classified.network:
            raise PolicyStop("policy")
        if is_tracker_host(classified.host):
            raise PolicyStop("tracker-blocked")
        parts = urlsplit(classified.url)
        scheme = parts.scheme.lower()
        host = parts.hostname or ""
        port = _target_port(scheme, parts.port)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        sock = tor.connect(host, port, timeout=timeout)
        tls_verified = scheme == "https" and not is_onion_host(host)
        try:
            if scheme == "https":
                ctx = tls_context_for(host)
                sock = ctx.wrap_socket(sock, server_hostname=host)
            status, ctype, body, location = _exchange(sock, host, port, path, timeout)
        finally:
            try:
                sock.close()
            except Exception:
                pass
        if status in {301, 302, 303, 307, 308} and location:
            nxt = urljoin(classified.url, location)
            again = classify_url(nxt)
            if not again.ok or not again.network or is_tracker_host(again.host):
                raise PolicyStop("tracker-blocked" if is_tracker_host(getattr(again, "host", "")) else "policy")
            current = again.url
            continue
        text_body = _decode(body, ctype)
        title = _title(text_body) if "html" in ctype.lower() or text_body.lstrip().startswith("<") else ""
        text = html_to_text(text_body) if "<" in text_body else text_body.strip()[:20000]
        return Page(
            url=classified.url,
            http_status=status,
            title=title,
            text=text,
            content_type=ctype,
            tls_verified=tls_verified,
            onion=classified.onion,
        )
    raise PolicyStop("redirects")
