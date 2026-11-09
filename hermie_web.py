"""Loopback-only Hermie game server. Run: python hermie_web.py"""
from __future__ import annotations

import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from hermie import interact, status

HOST = "127.0.0.1"
STATIC = Path(__file__).resolve().parent / "web"
TOKEN = secrets.token_urlsafe(24)

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data, kind="application/json; charset=utf-8"):
        body = json.dumps(data).encode() if not isinstance(data, bytes) else data
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        return secrets.compare_digest(self.headers.get("X-Hermie-Token", ""), TOKEN)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/pet":
            if not self._auth():
                return self._send(401, {"error": "Unauthorized"})
            return self._send(200, status())
        assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path not in assets:
            return self._send(404, {"error": "Not found"})
        filename, mime = assets[path]
        try:
            return self._send(200, (STATIC / filename).read_bytes(), mime)
        except OSError:
            return self._send(500, {"error": "Missing static assets"})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/action":
            return self._send(404, {"error": "Not found"})
        if not self._auth():
            return self._send(401, {"error": "Unauthorized"})
        # Reject cross-origin browser writes, including missing Origin.
        origin = self.headers.get("Origin", "")
        expected = "http://" + self.headers.get("Host", "")
        if origin != expected or not origin.startswith("http://127.0.0.1:"):
            return self._send(403, {"error": "Invalid origin"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n < 1 or n > 2048 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self._send(400, {"error": "Invalid request"})
            payload = json.loads(self.rfile.read(n))
            if not isinstance(payload, dict):
                raise ValueError("Expected object")
            pet = interact(payload.get("action"), payload.get("name"))
            return self._send(200, pet)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            return self._send(400, {"error": str(e)})

def main():
    port = int(os.environ.get("HERMIE_PORT", "8766"))
    server = ThreadingHTTPServer((HOST, port), Handler)
    print("Hermie home: http://%s:%d/#token=%s" % (HOST, server.server_port, TOKEN), flush=True)
    print("Keep this link private. The game is available only on your own computer.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
