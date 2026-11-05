"""
Second-screen dashboard: a tiny HTTP server (stdlib only) that serves one page
and streams live telemetry with Server-Sent Events. Open
http://<steam-machine-ip>:8090 on a phone or tablet on the same network.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
RATE_HZ = 15


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

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body: bytes, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    with open(os.path.join(WEB_DIR, "index.html"), "rb") as f:
                        self._send(200, f.read(), "text/html; charset=utf-8")
                elif self.path == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    try:
                        while True:
                            payload = json.dumps(hub.snapshot(), separators=(",", ":"))
                            self.wfile.write(f"data: {payload}\n\n".encode())
                            self.wfile.flush()
                            time.sleep(1 / RATE_HZ)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        return
                elif self.path == "/api/laps":
                    self._send(200, json.dumps(hub.store.recent(30)).encode(), "application/json")
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
                    self._send(200, json.dumps(hub.track_map()).encode(), "application/json")
                elif self.path == "/api/session":
                    self._send(200, json.dumps(hub.session_summary()).encode(), "application/json")
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
        if self.server:
            self.server.shutdown()
            self.server.server_close()
