"""Loopback browser bridge. The navigate proxy is Tor-only and fail-closed."""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from rx.engine import launch_isolated_engine
from rx.fence import PRIVATE_VIA_TOR, UNPRIVATE_UNLESS_TOR, routing_allowed
from rx.origin import BROWSER_HTML, ORIGIN_FILE, ORIGIN_URL_PATH
from rx.session import BrowseSession, NavResult

BOOT_DEFAULT = '{"token":"","engineProxied":false,"isolatedTorWebView":false}'
BRIDGE_HOST = "127.0.0.1"


def new_engine_mark() -> str:
    """Capability for the proxied engine process. Letters only, so it cannot be a port."""
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    return "rxe" + "".join(secrets.choice(alphabet) for _ in range(32))


def render_index(html: str, *, token: str, engine: bool) -> str:
    boot = json.dumps(
        {"token": token, "engineProxied": bool(engine), "isolatedTorWebView": False},
        separators=(",", ":"),
    )
    if BOOT_DEFAULT not in html:
        raise RuntimeError("browser html is missing the boot JSON marker")
    page = html.replace(BOOT_DEFAULT, boot, 1)
    if engine:
        page = page.replace("frame-src 'none'", "frame-src http: https:", 1)
    return page


def result_payload(result: NavResult) -> dict:
    return {
        "allowed": result.allowed,
        "blocked": result.blocked,
        "fetch": result.fetch,
        "status": result.status,
        "private": result.private,
        "url": result.url,
        "reason": result.reason,
        "onion": result.onion,
        "httpStatus": result.http_status,
        "title": result.title,
        "text": result.text,
        "contentType": result.content_type,
        "tlsVerified": result.tls_verified,
        "vpnRelay": False,
        "relay": "tor",
    }


def refused_payload(reason: str = "tor-down") -> dict:
    return {
        "allowed": False,
        "blocked": True,
        "fetch": False,
        "status": UNPRIVATE_UNLESS_TOR,
        "private": False,
        "url": "",
        "reason": reason,
        "onion": False,
        "vpnRelay": False,
        "relay": "tor",
        "launched": False,
    }


class BridgeServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler, session: BrowseSession, launcher=None):
        super().__init__(server_address, handler)
        self.session = session
        self.token = secrets.token_urlsafe(24)
        self.engine_nonce = secrets.token_urlsafe(24)
        self.engine_mark = new_engine_mark()
        self.launcher = launcher
        self.launch_count = 0


class Handler(BaseHTTPRequestHandler):
    server_version = "RxPrivacyBrowser/0.2"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def _raw(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._raw(code, raw, "application/json")

    def _authorized(self) -> bool:
        got = self.headers.get("X-Rx-Token") or ""
        want = self.server.token
        if len(got) != len(want):
            return False
        return secrets.compare_digest(got, want)

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        if parts.path == ORIGIN_URL_PATH:
            data = ORIGIN_FILE.read_bytes()
            self._raw(200, data, "application/json")
            return
        if parts.path == "/rx/status":
            self._json(200, self.server.session.status_payload())
            return
        if parts.path != "/":
            self._json(404, refused_payload("not-found"))
            return
        query = parse_qs(parts.query)
        nonce = (query.get("engine") or [""])[0]
        nonce_ok = (
            bool(nonce)
            and len(nonce) == len(self.server.engine_nonce)
            and secrets.compare_digest(nonce, self.server.engine_nonce)
        )
        ua = self.headers.get("User-Agent") or ""
        mark = self.server.engine_mark
        self.server.session.refresh()
        # Remote frames are enabled only for the proxied engine process, and
        # only while Tor is routing. Any other client keeps frame-src 'none'.
        engine = (
            nonce_ok
            and bool(mark)
            and mark in ua
            and routing_allowed(self.server.session.tor.state)
        )
        html = render_index(read_browser(), token=self.server.token, engine=engine)
        self._raw(200, html.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        parts = urlsplit(self.path)
        if not self._authorized():
            self._json(403, refused_payload("token"))
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length < 0 or length > 65536:
            self._json(400, refused_payload("body"))
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            incoming = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeError, json.JSONDecodeError):
            self._json(400, refused_payload("json"))
            return
        if parts.path == "/rx/navigate":
            result = self.server.session.navigate(str((incoming or {}).get("url") or ""))
            code = 200 if result.allowed and not result.blocked else 403
            self._json(code, result_payload(result))
            return
        if parts.path == "/rx/engine":
            self._launch_engine()
            return
        self._json(404, refused_payload("not-found"))

    def _launch_engine(self) -> None:
        session = self.server.session
        session.refresh()
        if not routing_allowed(session.tor.state):
            self._json(403, refused_payload("tor-down"))
            return
        host, port = self.server.server_address[:2]
        ui = f"http://{host}:{port}/?engine={self.server.engine_nonce}"
        socks_port = int(session.tor.state.socks_port)
        mark = self.server.engine_mark
        try:
            if self.server.launcher is not None:
                self.server.launcher(ui, socks_port, mark)
            else:
                launch_isolated_engine(
                    ui_url=ui,
                    socks_port=socks_port,
                    tor=session.tor,
                    engine_mark=mark,
                )
        except Exception:
            payload = result_payload(
                session.navigate("about:newtab")
            )
            payload["launched"] = False
            payload["status"] = PRIVATE_VIA_TOR
            payload["private"] = True
            payload["blocked"] = False
            self._json(200, payload)
            return
        self.server.launch_count += 1
        self._json(
            200,
            {
                "allowed": True,
                "blocked": False,
                "fetch": False,
                "status": PRIVATE_VIA_TOR,
                "private": True,
                "launched": True,
                "vpnRelay": False,
                "relay": "tor",
            },
        )


def read_browser() -> str:
    return BROWSER_HTML.read_text(encoding="utf-8")


def start_bridge(
    session: BrowseSession | None = None,
    host: str = BRIDGE_HOST,
    port: int = 8844,
    launcher=None,
) -> BridgeServer:
    if host != BRIDGE_HOST:
        raise RuntimeError("bridge must bind loopback only")
    httpd = BridgeServer((host, port), Handler, session or BrowseSession(), launcher)
    thread = threading.Thread(target=httpd.serve_forever, name="rx-bridge", daemon=True)
    thread.start()
    return httpd


def main(argv: list[str] | None = None) -> int:
    import argparse

    from rx.tor import LiveTor

    parser = argparse.ArgumentParser(description="Rx Privacy Browser Tor bridge")
    parser.add_argument("--port", type=int, default=8844)
    parser.add_argument("--no-spawn", action="store_true", help="Do not start a Tor daemon")
    parser.add_argument("--engine", action="store_true", help="Open the isolated Tor engine when a circuit is up")
    args = parser.parse_args(argv)
    tor = LiveTor()
    if args.no_spawn:
        tor.refresh()
    else:
        tor.ensure()
    session = BrowseSession(tor)
    httpd = start_bridge(session, port=args.port)
    host, port = httpd.server_address[:2]
    print(f"rx-bridge http://{host}:{port}/")
    print(f"origin http://{host}:{port}{ORIGIN_URL_PATH}")
    print(f"status={session.status_line()}")
    print("vpn_relay=false")
    print("galleryReady=false")
    if args.engine and routing_allowed(tor.state):
        try:
            launch_isolated_engine(
                ui_url=f"http://{host}:{port}/?engine={httpd.engine_nonce}",
                socks_port=int(tor.state.socks_port),
                tor=tor,
                engine_mark=httpd.engine_mark,
            )
            print("engine=started")
        except Exception as exc:
            print(f"engine=not-started {exc}")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        tor.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
