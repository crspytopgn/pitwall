#!/usr/bin/env python3
"""Standalone Pitwall: the same backend as the Decky plugin, without Decky.

Runs as a system service (root, like Decky runs plugins: wheel settings, udev
rules and driver installs need it) on behalf of one desktop user.

- Phone dashboard: http://<this machine>:8090 on your network, as in the plugin
- Control app:     http://127.0.0.1:8091 on this machine only

The control app can change system settings, so it only listens on localhost,
only answers requests addressed to localhost (no DNS rebinding) and only
accepts API calls carrying a custom header, which other websites open in your
browser can't send (no cross-site requests).

Usage:  pitwall_app.py [--user NAME] [--port 8091]
        pitwall_app.py --cleanup      undo system changes (used by uninstall.sh)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pwd
import queue
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION = "0.1.0"
CONTROL_PORT = 8091
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
log = logging.getLogger("pitwall")


# ---------------------------------------------------------------- decky shim
class Events:
    """Messages the backend sends to the UI (toasts), fanned out to every open app tab."""

    def __init__(self):
        self.lock = threading.Lock()
        self.subs: list[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.subs.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subs:
                self.subs.remove(q)

    def publish(self, event: str, *args):
        with self.lock:
            for q in self.subs:
                try:
                    q.put_nowait({"event": event, "args": list(args)})
                except queue.Full:
                    pass


def user_paths(user: str) -> dict:
    pw = pwd.getpwnam(user)
    home = pw.pw_dir
    return {"home": home, "uid": pw.pw_uid, "gid": pw.pw_gid,
            "settings": os.path.join(home, ".config", "pitwall"),
            "data": os.path.join(home, ".local", "share", "pitwall", "app"),
            "logs": os.path.join(home, ".local", "state", "pitwall")}


def give_to_user(paths: dict):
    """The service runs as root, but everything it keeps in your home folder
    should belong to you: the folders (and their parents up to home) and the
    files in them."""
    home = paths["home"]
    for k in ("settings", "data", "logs"):
        d = paths[k]
        chain = []
        while d.startswith(home + os.sep):
            chain.append(d)
            d = os.path.dirname(d)
        for p in chain:
            try:
                if os.stat(p).st_uid != paths["uid"]:
                    os.chown(p, paths["uid"], paths["gid"])
            except OSError:
                pass
        for dirpath, dirs, files in os.walk(paths[k]):
            for n in dirs + files:
                p = os.path.join(dirpath, n)
                try:
                    if os.lstat(p).st_uid != paths["uid"]:
                        os.lchown(p, paths["uid"], paths["gid"])
                except OSError:
                    pass


def install_shim(user: str, events: Events) -> dict:
    paths = user_paths(user)
    for k in ("settings", "data", "logs"):
        os.makedirs(paths[k], exist_ok=True)
    give_to_user(paths)
    d = types.ModuleType("decky")
    d.DECKY_PLUGIN_SETTINGS_DIR = paths["settings"]
    d.DECKY_PLUGIN_RUNTIME_DIR = paths["data"]
    d.DECKY_PLUGIN_LOG_DIR = paths["logs"]
    d.DECKY_USER_HOME = paths["home"]
    d.DECKY_USER = user
    d.DECKY_PLUGIN_VERSION = VERSION
    d.DECKY_PLUGIN_NAME = "Pitwall"
    d.logger = log

    async def emit(event, *args):
        events.publish(event, *args)
    d.emit = emit
    sys.modules["decky"] = d
    return paths


def default_user() -> str:
    for env in ("PITWALL_USER", "SUDO_USER"):
        u = os.environ.get(env)
        if u:
            return u
    try:
        return pwd.getpwuid(1000).pw_name
    except KeyError:
        return pwd.getpwuid(os.getuid()).pw_name


def decky_pitwall_running(home: str) -> bool:
    """Both versions would fight over the wheel and the dashboard port."""
    if not os.path.isdir(os.path.join(home, "homebrew", "plugins", "Pitwall")):
        return False
    from steam import _cmdlines  # local module
    return any(b"PluginLoader" in b" ".join(a) or any(x.endswith(b"PluginLoader") for x in a) for _p, a in _cmdlines())


# -------------------------------------------------------------------- app
class App:
    # Methods the web app may call, besides the plugin's own public methods.
    EXTRA = ("app_info", "running_game", "launch_options_get", "launch_options_set", "launch_options_pending",
             "graphics_options_set")

    def __init__(self, user: str, port: int = CONTROL_PORT):
        self.user, self.port = user, port
        self.events = Events()
        self.paths = install_shim(user, events=self.events)
        sys.path.insert(0, ROOT)
        sys.path.insert(0, HERE)
        import main  # the Decky backend, unchanged
        import steam
        self.main, self.steam = main, steam
        self.plugin = main.Plugin()
        self.launch = steam.LaunchOptions(self.paths["home"], os.path.join(self.paths["data"], "launch-queue.json"),
                                          uid=self.paths["uid"], gid=self.paths["gid"])
        self.loop = asyncio.new_event_loop()
        self.game: dict | None = None
        self.stop = threading.Event()
        self.server = None

    # ---- extra API for things the Decky UI got from the Steam client
    async def app_info(self) -> dict:
        return {"version": VERSION, "user": self.user, "standalone": True,
                "steam_running": self.steam.steam_running(), "game": self.game,
                "pending_launch_options": len(self.launch.pending())}

    async def running_game(self) -> dict | None:
        return self.game

    async def launch_options_get(self, appid: str) -> str | None:
        return self.launch.get(str(appid))

    async def launch_options_set(self, appid: str, opts: str) -> dict:
        if not isinstance(opts, str) or len(opts) > 4000:
            return {"ok": False, "applied": False, "message": "Invalid launch options."}
        return self.launch.set(str(appid), opts)

    async def launch_options_pending(self) -> dict:
        return self.launch.pending()

    # ---- watchers
    def _watch(self):
        """Every 2 s: which game is running (for profiles and checks), and apply
        queued launch options once Steam has exited."""
        last = None
        tick = 0
        while not self.stop.wait(2):
            tick += 1
            if tick % 15 == 1:            # every 30 s
                give_to_user(self.paths)
            try:
                appid = self.steam.running_game()
                if appid != last:
                    if last:
                        self.call("game_changed", [last, (self.game or {}).get("name", ""), False])
                    self.game = None
                    if appid:
                        name = self.steam.app_name(self.paths["home"], appid) or f"App {appid}"
                        self.game = {"appid": appid, "name": name}
                        r = self.call("game_changed", [appid, name, True]) or {}
                        if (r.get("graphics") or {}).get("enrolled"):
                            self._graphics_options(appid)
                        if r.get("applied"):
                            self.events.publish("pitwall_toast", f"Applied wheel profile: {r['applied']}")
                        g = r.get("game") or {}
                        if g.get("status") == "broken":
                            self.events.publish("pitwall_toast", f"{g.get('name')} is known not to run on SteamOS. See the game guide.")
                    last = appid
                if self.launch.pending() and not self.steam.steam_running():
                    r = self.launch.flush()
                    if r.get("applied"):
                        self.events.publish("pitwall_toast", r["message"])
            except Exception:
                log.exception("Watcher error")

    def _graphics_options(self, appid: str, enable: bool = True):
        """Frame cap and quiet measuring for a tuned game. Written now if Steam
        allows, otherwise queued for when Steam closes; used from the next start."""
        cur = self.launch.get(str(appid))
        if cur is None:
            return
        nxt = self.call("graphics_launch_options", [str(appid), cur, enable])
        if isinstance(nxt, str) and nxt != cur:
            self.launch.set(str(appid), nxt)

    async def graphics_options_set(self, appid: str, enable: bool) -> dict:
        await asyncio.get_running_loop().run_in_executor(None, self._graphics_options, str(appid), bool(enable))
        return {"ok": True}

    def call(self, name: str, args: list, timeout: float = 600):
        if name in self.EXTRA:
            fn = getattr(self, name)
        else:
            fn = getattr(self.plugin, name, None)
        fut = asyncio.run_coroutine_threadsafe(fn(*args), self.loop)
        return fut.result(timeout)

    def allowed(self, name: str) -> bool:
        if name in self.EXTRA:
            return True
        if name.startswith("_"):
            return False
        fn = getattr(self.plugin, name, None)
        return fn is not None and asyncio.iscoroutinefunction(fn)

    # ---- HTTP
    def serve(self):
        app = self
        page = os.path.join(HERE, "app.html")
        assets = {"qrcode.js": ("vendor/qrcode.js", "text/javascript"), "logo.svg": ("../assets/mark.svg", "image/svg+xml")}

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _host_ok(self) -> bool:
                host = (self.headers.get("Host") or "").rsplit(":", 1)[0].lower()
                return host in LOCAL_HOSTS

            def _send(self, code, body: bytes, ctype="application/json", extra=None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, b"Forbidden", "text/plain")
                path = self.path.split("?", 1)[0]
                if path in ("/", "/index.html"):
                    with open(page, "rb") as f:
                        return self._send(200, f.read(), "text/html; charset=utf-8",
                                          {"Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                           "script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"})
                if path.lstrip("/") in assets:
                    rel, ctype = assets[path.lstrip("/")]
                    try:
                        with open(os.path.normpath(os.path.join(HERE, rel)), "rb") as f:
                            return self._send(200, f.read(), ctype)
                    except OSError:
                        return self._send(404, b"Not found", "text/plain")
                if path == "/api/events":
                    q = app.events.subscribe()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    try:
                        while not app.stop.is_set():
                            try:
                                msg = q.get(timeout=15)
                                self.wfile.write(f"data: {json.dumps(msg)}\n\n".encode())
                            except queue.Empty:
                                self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                    except OSError:
                        pass
                    finally:
                        app.events.unsubscribe(q)
                    self.close_connection = True
                    return
                return self._send(404, b"Not found", "text/plain")

            def do_POST(self):
                if not self._host_ok():
                    return self._send(403, b'{"error":"forbidden"}')
                if self.headers.get("X-Pitwall") != "1":
                    return self._send(403, b'{"error":"missing header"}')
                if not self.path.startswith("/api/call/"):
                    return self._send(404, b'{"error":"not found"}')
                name = self.path[len("/api/call/"):]
                if not app.allowed(name):
                    return self._send(404, b'{"error":"unknown method"}')
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > 65536:
                        return self._send(413, b'{"error":"too large"}')
                    body = json.loads(self.rfile.read(n) or b"{}")
                    args = body.get("args", [])
                    if not isinstance(args, list):
                        raise ValueError("args must be a list")
                except (ValueError, json.JSONDecodeError):
                    return self._send(400, b'{"error":"bad request"}')
                try:
                    result = app.call(name, args)
                    from pitwall.dashboard import safe_json
                    return self._send(200, safe_json({"result": result}).encode())
                except TypeError as e:
                    return self._send(400, json.dumps({"error": f"bad arguments: {e}"}).encode())
                except Exception as e:
                    log.exception("API call %s failed", name)
                    return self._send(500, json.dumps({"error": str(e)}).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def run(self):
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        asyncio.run_coroutine_threadsafe(self.plugin._main(), self.loop).result(60)
        self.serve()
        threading.Thread(target=self._watch, daemon=True).start()
        log.info("Pitwall %s standalone for %s: control app http://127.0.0.1:%d", VERSION, self.user, self.port)

    def shutdown(self):
        self.stop.set()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        try:
            asyncio.run_coroutine_threadsafe(self.plugin._unload(), self.loop).result(15)
        except Exception:
            log.exception("Unload failed")
        self.loop.call_soon_threadsafe(self.loop.stop)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pitwall standalone")
    ap.add_argument("--user", default=None)
    ap.add_argument("--port", type=int, default=CONTROL_PORT)
    ap.add_argument("--cleanup", action="store_true", help="undo Pitwall's system changes and exit")
    ap.add_argument("--allow-with-decky", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    user = a.user or default_user()

    if a.cleanup:
        events = Events()
        install_shim(user, events)
        sys.path.insert(0, ROOT)
        sys.path.insert(0, HERE)
        import main as backend
        asyncio.run(backend.Plugin()._uninstall())
        print("Removed Pitwall's wheel detection rule and any drivers it installed.")
        return 0

    sys.path.insert(0, HERE)
    if not a.allow_with_decky and decky_pitwall_running(user_paths(user)["home"]):
        log.error("The Pitwall Decky plugin is installed and Decky is running. Use one or the other: "
                  "remove the plugin in Decky, or start this with --allow-with-decky.")
        return 2

    app = App(user, a.port)
    app.run()
    import signal
    done = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: done.set())
    done.wait()
    app.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
