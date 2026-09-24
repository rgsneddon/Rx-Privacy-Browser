"""Serve the pinned vortice body as exact bytes. This server does not proxy traffic."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from rx.fence import ORIGIN_URL_PATH
from rx.origin import ORIGIN_FILE


class OriginHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if urlsplit(self.path).path != ORIGIN_URL_PATH:
            body = b"not found\n"
            self.send_response(404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data = ORIGIN_FILE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve the Rx Privacy Browser Continuum origin body (exact bytes, no proxy)"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), OriginHandler)
    print(f"origin http://{args.host}:{args.port}{ORIGIN_URL_PATH}")
    print("bytes must be served unchanged; a new body needs a new vort1 key")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
