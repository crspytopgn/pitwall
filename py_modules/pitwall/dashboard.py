"""
Second-screen dashboard: a tiny HTTP server (stdlib only) that serves one page
and streams live telemetry with Server-Sent Events. Open
http://<steam-machine-ip>:8090 on a phone or tablet on the same network.
"""

from __future__ import annotations

import json
import math
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
RATE_HZ = 15
# Small static files the page needs (home-screen icons, manifest, keep-awake video).
STATIC = {"/icon-180.png": "image/png", "/icon-192.png": "image/png", "/icon-512.png": "image/png",
          "/icon-maskable.png": "image/png", "/keepawake.mp4": "video/mp4"}
def _finite(o):
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    return o


def safe_json(o) -> str:
    """Strict JSON for the browser: NaN/inf would make JSON.parse throw and
    freeze the dashboard, so they become null."""
    try:
        return json.dumps(o, separators=(",", ":"), allow_nan=False)
    except ValueError:
        return json.dumps(_finite(o), separators=(",", ":"), allow_nan=False)


MANIFEST = json.dumps({
    "name": "Pitwall", "short_name": "Pitwall", "start_url": "/", "scope": "/", "display": "standalone",
    "orientation": "any", "background_color": "#000000", "theme_color": "#000000",
    "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
              {"src": "/icon-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
}).encode()


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no packet is sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Dashboard:
    def __init__(self, hub, port: int = 8090, downloads=None):
        self.hub, self.port = hub, port
        self.downloads = downloads          # diagnostics.DownloadTokens
        self.server: ThreadingHTTPServer | None = None
        self.error: str | None = None

    @property
    def url(self) -> str:
        return f"http://{local_ip()}:{self.port}"

    def start(self):
        hub = self.hub
        downloads = self.downloads
        self._stopping = stopping = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body: bytes, ctype, cache="no-store"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", cache)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    with open(os.path.join(WEB_DIR, "index.html"), "rb") as f:
                        self._send(200, f.read(), "text/html; charset=utf-8")
                elif self.path in STATIC:
                    with open(os.path.join(WEB_DIR, self.path[1:]), "rb") as f:
                        self._send(200, f.read(), STATIC[self.path], "max-age=86400")
                elif self.path == "/manifest.webmanifest":
                    self._send(200, MANIFEST, "application/manifest+json", "max-age=86400")
                elif self.path == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    try:
                        while not stopping.is_set():
                            snap = hub.snapshot()
                            self.wfile.write(f"data: {safe_json(snap)}\n\n".encode())
                            self.wfile.flush()
                            # Full rate while driving; a slow heartbeat when nothing's running.
                            stopping.wait(1 / RATE_HZ if snap.get("receiving") else 0.5)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return
                elif self.path == "/api/laps":
                    self._send(200, safe_json(hub.store.recent(30)).encode(), "application/json")
                elif self.path.startswith("/diag/") and downloads is not None:
                    path = downloads.take(self.path[len("/diag/"):])
                    if not path or not os.path.exists(path):
                        self._send(404, b"This link has expired. Create a new diagnostics bundle in Pitwall.", "text/plain")
                        return
                    with open(path, "rb") as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif self.path == "/api/track":
                    self._send(200, safe_json(hub.track_map()).encode(), "application/json")
                elif self.path == "/api/session":
                    self._send(200, safe_json(hub.session_summary()).encode(), "application/json")
                else:
                    self._send(404, b"not found", "text/plain")

        try:
            self.server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
            self.server.daemon_threads = True
        except OSError as e:
            self.error = f"Dashboard can't use port {self.port}: {e.strerror}"
            return
        threading.Thread(target=self.server.serve_forever, daemon=True, name="dashboard").start()

    def stop(self):
        if getattr(self, "_stopping", None):
            self._stopping.set()          # ends open /events streams
        if self.server:
            self.server.shutdown()
            self.server.server_close()
