"""Pitwall Decky backend: wires the pitwall package to the Quick Access UI."""

import asyncio
import json
import math
import os
import sys
import threading

import decky  # provided by Decky Loader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "py_modules"))

from pitwall import compat as compat_mod  # noqa: E402
from pitwall import bridge, buttons, device, diagnostics, drivers, engineer, ffb, ffbtest, gamebinds, graphics, health, perf, updates, vpad  # noqa: E402
from pitwall.dashboard import Dashboard  # noqa: E402
from pitwall.hub import Hub  # noqa: E402
from pitwall.leds import RevLights  # noqa: E402
from pitwall.wheels import detect_wheel  # noqa: E402

SETTINGS_DIR = decky.DECKY_PLUGIN_SETTINGS_DIR
DATA_DIR = decky.DECKY_PLUGIN_RUNTIME_DIR
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
HOME = decky.DECKY_USER_HOME
MANGOHUD_DIR = os.path.join(HOME, ".local", "share", "pitwall", "mangohud")

DEFAULTS = {
    "auto_apply": True,
    "wheel_default": None,          # {"settings": {...}}
    "wheel_games": {},              # appid -> {"name", "settings"}
    "wheel_cars": {},               # "sim:car" -> {"name", "sim", "settings"}; overrides the game profile
    "target_fps": 60,
    "units": "kmh",
    "dashboard_port": 8090,
    "ports": {},                    # overrides for telemetry ports
    "anthropic_api_key": "",
    "rev_lights": False,            # drive MOZA wheel rev lights from telemetry
    "setup_done": False,            # first-run auto setup has been run or dismissed
    "check_updates": True,          # daily check for driver and bridge updates (GitHub, read-only)
    "nav_enabled": True,            # wheel buttons drive Steam's menus when no game is running
    "nav_map": {},                  # Steam action -> wheel control; empty means the automatic layout
    "game_layout": {},              # in-game action -> wheel control (your choices; the rest is automatic)
    "beamng_auto": True,            # write the layout into BeamNG.drive's controls
    "auto_graphics": True,          # tune graphics for every recognised game, measured on this machine
}

PROFILE_EXCLUDE = {"ffb_enabled"}
VERSION = getattr(decky, "DECKY_PLUGIN_VERSION", "0.1.0")   # never let a profile silently switch FFB off


def _load() -> dict:
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    import copy
    return {**copy.deepcopy(DEFAULTS), **data}


def _chown_to_user(*paths):
    try:
        import pwd
        pw = pwd.getpwnam(decky.DECKY_USER)
        for p in paths:
            os.chown(p, pw.pw_uid, pw.pw_gid)
    except (KeyError, OSError, AttributeError):
        pass


def _chown_tree_to_user(paths):
    """Files Pitwall writes into a game's folders belong to you, not root."""
    for p in paths:
        for q in (p, p + ".pitwall", p + ".pitwall-backup", os.path.dirname(p)):
            if os.path.exists(q):
                _chown_to_user(q)


def _save(data: dict):
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp, 0o600)        # may hold an API key
    os.replace(tmp, SETTINGS_FILE)


class Plugin:
    async def _run(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(None, fn, *args)

    # ================================================================ wheel
    def _wheel(self):
        # Called from several worker threads (UI calls, rev lights): only one
        # may detect/open the wheel at a time.
        with self.wheel_lock:
            if self.wheel is None or not self.wheel.detect():
                if self.wheel:
                    self.wheel.close()
                self.wheel = detect_wheel(decky.logger, os.environ.get("PITWALL_MOZA_TTY"))
            return self.wheel

    async def wheel_status(self) -> dict:
        w = await self._run(self._wheel)
        if not w:
            from pitwall.wheels import moza as moza_mod
            p = await self._run(moza_mod.probe)
            if p["state"] != "none":
                return {"connected": False, "error": p["detail"], "moza": p["state"]}
            return {"connected": False, "error": "No controllable wheel found. Pitwall supports MOZA, Logitech, Fanatec "
                    "(hid-fanatecff) and Thrustmaster (hid-tmff2). Check the base is switched on and plugged in by USB."}
        return {"connected": True, "name": w.name, "brand": w.brand, "settings": w.settings(),
                "can_center": w.brand == "MOZA", "leds": bool(getattr(w, "leds_supported", False)),
                "rev_lights": bool(self.settings.get("rev_lights"))}

    async def wheel_read(self):
        w = await self._run(self._wheel)
        return await self._run(w.read_all) if w else None

    async def wheel_set(self, key: str, value: float) -> bool:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(value) or not isinstance(key, str):
            return False
        w = await self._run(self._wheel)
        return bool(w) and await self._run(w.write, {key: value})

    async def wheel_center(self) -> bool:
        w = await self._run(self._wheel)
        return bool(w) and await self._run(w.center)

    async def get_profiles(self) -> dict:
        s = self.settings
        st = self.hub.status()
        car_key = f"{st['sim']}:{st['car']}" if st.get("sim") and st.get("car") else None
        return {"auto_apply": s["auto_apply"], "has_default": s["wheel_default"] is not None,
                "games": {k: v.get("name", k) for k, v in s["wheel_games"].items()},
                "cars": {k: v.get("name", k) for k, v in s["wheel_cars"].items()},
                "current_car": {"key": car_key, "name": st.get("car"), "sim": st.get("sim")} if car_key else None}

    async def set_auto_apply(self, enabled: bool):
        self.settings["auto_apply"] = bool(enabled)
        _save(self.settings)

    async def save_profile(self, appid: str, name: str) -> bool:
        values = await self.wheel_read()
        if not values:
            return False
        values = {k: v for k, v in values.items() if k not in PROFILE_EXCLUDE}
        if appid == "default":
            self.settings["wheel_default"] = {"settings": values}
        elif str(appid).startswith("car:"):
            key = str(appid)[4:]
            self.settings["wheel_cars"][key] = {"name": name, "sim": key.split(":", 1)[0], "settings": values}
        else:
            self.settings["wheel_games"][str(appid)] = {"name": name, "settings": values}
        _save(self.settings)
        return True

    async def delete_profile(self, appid: str):
        if appid == "default":
            self.settings["wheel_default"] = None
        elif str(appid).startswith("car:"):
            self.settings["wheel_cars"].pop(str(appid)[4:], None)
        else:
            self.settings["wheel_games"].pop(str(appid), None)
        _save(self.settings)

    async def apply_profile(self, appid: str) -> bool:
        s = self.settings
        if appid == "default":
            prof = s["wheel_default"]
        elif str(appid).startswith("car:"):
            prof = s["wheel_cars"].get(str(appid)[4:])
        else:
            prof = s["wheel_games"].get(str(appid))
        w = await self._run(self._wheel)
        if not prof or not w:
            return False
        return await self._run(w.write, prof["settings"])

    async def game_changed(self, appid: str, name: str, running: bool) -> dict:
        """Frontend hook for game start/stop. Applies wheel profiles and
        returns what happened plus the compatibility entry for the game."""
        appid = str(appid)
        result = {"applied": None, "game": None}
        if running:
            self.current_app = {"appid": appid, "name": name}
        elif self.current_app and self.current_app["appid"] == appid:
            self.current_app = None
        else:
            return result
        self.hub.reset_car()          # so a car profile re-applies after the game/default profile
        self.nav.set_in_game(self.current_app is not None)
        if not running and appid == gamebinds.BEAMNG_APPID:
            await self._run(self._beamng_sync)     # ready for next time, if the layout changed
        g = self.compat.find(appid, name)
        result["game"] = {"id": g["id"], "name": g["name"], "status": g["status"]} if g else None
        result["graphics"] = await self._graphics_game(appid, name, running, g)
        if self.settings["auto_apply"]:
            if running and appid in self.settings["wheel_games"]:
                if await self.apply_profile(appid):
                    result["applied"] = self.settings["wheel_games"][appid].get("name", appid)
            elif not running and self.settings["wheel_default"]:
                if await self.apply_profile("default"):
                    result["applied"] = "Default"
        return result

    # ============================================================ FFB feel
    async def ffb_catalogue(self) -> dict:
        cat = ffb.catalogue()
        g = self.compat.find(self.current_app["appid"], self.current_app["name"]) if self.current_app else None
        cat["ingame"] = (g or {}).get("ffb_ingame")
        cat["game"] = g["name"] if g else None
        cat["can_undo"] = bool(self.ffb_undo_stack)
        return cat

    async def _ffb_write(self, values: dict) -> dict:
        w = await self._run(self._wheel)
        if not w:
            return {"ok": False, "message": "No wheel connected"}
        before = await self._run(w.read_all)
        if not before:
            return {"ok": False, "message": "Couldn't read the wheel's current settings"}
        values = {k: v for k, v in values.items() if k in before}
        if not values:
            return {"ok": False, "message": "Nothing to change on this wheel"}
        self.ffb_undo_stack.append({k: before[k] for k in values})
        del self.ffb_undo_stack[:-10]
        ok = await self._run(w.write, values)
        return {"ok": ok, "applied": values}

    async def ffb_apply_preset(self, preset_id: str) -> dict:
        w = await self._run(self._wheel)
        if not w:
            return {"ok": False, "message": "No wheel connected"}
        vals = ffb.preset_values(preset_id, w.settings())
        if vals is None:
            return {"ok": False, "message": "Unknown preset"}
        return await self._ffb_write(vals)

    async def ffb_nudge(self, symptom: str) -> dict:
        w = await self._run(self._wheel)
        if not w:
            return {"ok": False, "message": "No wheel connected"}
        cur = await self._run(w.read_all)
        if not cur:
            return {"ok": False, "message": "Couldn't read the wheel's current settings"}
        sim = (self.hub.status() or {}).get("sim")
        n = ffb.nudge(symptom, cur, w.settings(), sim)
        if n is None:
            return {"ok": False, "message": "Unknown symptom"}
        res = {"ok": True, "changes": n["changes"], "tip": n["tip"], "source": n["source"]}
        if n["values"]:
            res.update(await self._ffb_write(n["values"]))
            res["changes"] = n["changes"]
        return res

    async def ffb_undo(self) -> dict:
        if not self.ffb_undo_stack:
            return {"ok": False, "message": "Nothing to undo"}
        w = await self._run(self._wheel)
        if not w:
            return {"ok": False, "message": "No wheel connected"}
        prev = self.ffb_undo_stack.pop()
        return {"ok": await self._run(w.write, prev), "applied": prev}

    def _on_car_change(self, sim: str, car: str):
        """Telemetry thread: a new car appeared. Apply its profile if saved."""
        key = f"{sim}:{car}"
        prof = self.settings["wheel_cars"].get(key)
        if not (self.settings["auto_apply"] and prof):
            return

        def apply():
            w = self._wheel()
            if w and w.write(prof["settings"]):
                self._emit("pitwall_toast", f"Applied wheel profile for {prof.get('name', car)}")
        threading.Thread(target=apply, daemon=True).start()

    def _emit(self, event: str, *args):
        try:
            asyncio.run_coroutine_threadsafe(decky.emit(event, *args), self.loop)
        except Exception:
            pass

    # ========================================================== strategy
    async def strategy_report(self) -> dict:
        return self.hub.strategy.report()

    async def strategy_set_target(self, laps: float, minutes: float) -> dict:
        def num(v, hi):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return None
            return v if 0 < v <= hi else None
        self.hub.strategy.set_target(num(laps, 1000), num(minutes, 48 * 60))
        return self.hub.strategy.report()

    # ======================================================== auto setup
    def _games_installed(self) -> list[dict]:
        inst = compat_mod.installed_appids(HOME)
        return [{**g, "installed": bool(g.get("steam_appid") and g["steam_appid"] in inst)}
                for g in self.compat.data["games"]]

    async def auto_setup_plan(self) -> dict:
        w = await self._run(self._wheel)
        dev = await self._run(device.detect)
        games = await self._run(self._games_installed)
        out = device.plan(dev, w, games, ffb.preset_for_base)
        out["first_run"] = not self.settings.get("setup_done")
        return out

    async def auto_setup_apply(self) -> dict:
        p = await self.auto_setup_plan()
        results = []
        if p["preset"]:
            r = await self.ffb_apply_preset(p["preset"])
            results.append({"step": "wheel", "ok": r.get("ok", False), "detail": r.get("message") or f"Applied {p['preset']}"})
        self.settings["target_fps"] = p["target_fps"]
        results.append({"step": "fps", "ok": True, "detail": f"Target {p['target_fps']} FPS"})
        for g in await self._run(self._games_installed):
            if g.get("installed") and g.get("auto_setup"):
                r = await self.compat_auto_setup(g["id"])
                results.append({"step": f"game:{g['id']}", "ok": r["ok"], "detail": f"{g['name']}: {r['message']}"})
        self.settings["setup_done"] = True
        _save(self.settings)
        return {"results": results, "bridge_games": [g["id"] for g in await self._run(self._games_installed)
                                                     if g.get("installed") and g.get("bridge_auto")]}

    async def dismiss_first_run(self):
        self.settings["setup_done"] = True
        _save(self.settings)

    # ======================================================= diagnostics
    async def diagnostics_create(self) -> dict:
        checks = await self.health_check()
        w = self.wheel
        info = diagnostics.collect(VERSION, self.settings, self.hub, w, checks, getattr(decky, "DECKY_PLUGIN_LOG_DIR", None))
        logs = diagnostics.log_tail(getattr(decky, "DECKY_PLUGIN_LOG_DIR", None))
        uid = gid = None
        try:
            import pwd
            pw = pwd.getpwnam(decky.DECKY_USER)
            uid, gid = pw.pw_uid, pw.pw_gid
        except (KeyError, ImportError, AttributeError):
            pass
        path = await self._run(lambda: diagnostics.write_zip(info, logs, HOME, uid, gid))
        tok = self.downloads.issue(path)
        return {"path": path, "summary": diagnostics.summary_text(info),
                "download_url": f"{self.dashboard.url}/diag/{tok}" if not self.dashboard.error else None,
                "issue_url": diagnostics.issue_url(info)}

    # ============================================================ telemetry
    async def session_status(self) -> dict:
        st = self.hub.status()
        st["dashboard_url"] = self.dashboard.url if not self.dashboard.error else None
        st["dashboard_error"] = self.dashboard.error
        return st

    async def set_start_line(self) -> bool:
        return self.hub.set_start_line()

    async def recent_laps(self) -> list:
        return await self._run(self.hub.store.recent, 15)

    # ========================================================== compat guide
    async def compat_list(self) -> list:
        return await self._run(self.compat.overview)

    async def compat_detail(self, game_id: str) -> dict:
        return await self._run(self.compat.detail, game_id)

    async def compat_auto_setup(self, game_id: str) -> dict:
        return await self._run(self.compat.run_auto_setup, game_id)

    async def compat_for_app(self, appid: str, name: str):
        g = self.compat.find(appid, name)
        return g["id"] if g else None

    # ============================================================== bridge
    async def bridge_status(self, appid: str) -> dict:
        try:
            ok_app = int(appid) in bridge.SUPPORTED_APPIDS
        except (TypeError, ValueError):
            ok_app = False
        return {"supported": ok_app, "installed": bridge.installed(HOME), "prefix": bridge.launch_prefix(HOME)}

    async def bridge_install(self) -> dict:
        uid = gid = None
        try:
            import pwd
            pw = pwd.getpwnam(decky.DECKY_USER)
            uid, gid = pw.pw_uid, pw.pw_gid
        except (KeyError, ImportError, AttributeError):
            pass
        return await self._run(lambda: bridge.install(HOME, uid, gid))

    async def bridge_launch_options(self, current: str, enable: bool) -> str:
        prefix = bridge.launch_prefix(HOME)
        return bridge.merge_launch_options(current, prefix) if enable else bridge.remove_from_launch_options(current, prefix)

    # ===================================================== wheel detection
    async def wheel_detection(self) -> dict:
        """Connected wheel bases and the two detection fixes Pitwall can apply."""
        def go():
            devs = health.input_wheels()
            bases = list({(d["vid"], d["pid"]): d for d in devs}.values())
            return {"wheels": [{"name": d["name"], "vid": d["vid"], "pid": d["pid"], "joystick": d["joystick"],
                                "model": (d["known"] or {}).get("model"), "brand": d["brand"]} for d in bases],
                    "needs_hwdb": any(d["joystick"] is False for d in bases),
                    "sdl_value": health.sdl_wheel_env(bases)}
        return await self._run(go)

    async def wheel_detection_fix(self) -> dict:
        return await self._run(lambda: health.apply_joystick_fix(health.input_wheels()))

    async def wheel_launch_options(self, current: str, enable: bool) -> str:
        value = health.sdl_wheel_env(health.input_wheels())
        return health.sdl_launch_options(current, value, enable)

    # ===================================================== force feedback setup
    async def ffb_status(self) -> dict:
        """Each wheel base: whether it has force feedback, which effects its driver
        supports, and the driver Pitwall can install if it needs one."""
        def go():
            has_upidff = health.kernel_has_universal_pidff()
            st = self.drivers.status()
            out = []
            for d in health.input_wheels():
                known = d.get("known") or {}
                caps = ffbtest.caps_summary(ffbtest.parse_caps(health.ff_caps(d["event"])))
                need = drivers.driver_for(known, has_upidff)
                inst = st["installed"].get(need) if need else None
                # A driver that's installed and loaded isn't "needed" any more, unless FFB is still missing.
                if need and inst and inst["present"] and d["ffb"] and need != "new-lg4ff":
                    need = None
                if need == "new-lg4ff" and inst and inst["present"]:
                    need = None
                out.append({"event": d["event"], "name": d["name"], "brand": d["brand"],
                            "model": known.get("model"), "rank": known.get("rank"), "ffb": d["ffb"],
                            "caps": caps, "driver": known.get("driver"),
                            "need": need and {"id": need, **{k: drivers.DRIVERS[need][k] for k in ("name", "repo", "for")}}})
            # Pedals and shifters have no FFB of their own; list bases first.
            out.sort(key=lambda x: (not x["ffb"] and not x["need"], x["name"]))
            return {"devices": out, "steamos": st["steamos"], "kernel": st["kernel"],
                    "installed": st["installed"], "job": st["job"]}
        return await self._run(go)

    async def ffb_test(self, event: str, strength: float = 0.2) -> dict:
        if not event.startswith("event") or not event[5:].isdigit():
            return {"ok": False, "message": "Unknown device."}
        try:
            strength = float(strength)
        except (TypeError, ValueError):
            strength = 0.2
        return await self._run(ffbtest.run_test, f"/dev/input/{event}", strength)

    async def driver_install(self, driver_id: str) -> dict:
        return self.drivers.start(driver_id, "install")

    async def driver_remove(self, driver_id: str) -> dict:
        return self.drivers.start(driver_id, "remove")

    async def driver_job(self) -> dict | None:
        return self.drivers.job_view()

    async def hidraw_launch_options(self, current: str, enable: bool) -> str:
        value = health.sdl_wheel_env(health.input_wheels())
        return health.env_launch_options(current, "PROTON_ENABLE_HIDRAW", value, enable)

    # ============================================================ updates
    UPDATES_FILE = os.path.join(DATA_DIR, "updates.json")

    def _updates_cached(self) -> dict | None:
        try:
            with open(self.UPDATES_FILE) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _updates_run(self) -> dict:
        res = updates.check(self.drivers.state(), drivers.DRIVERS, bridge.installed(HOME), bridge.installed_version(HOME))
        prev = self._updates_cached() or {}
        res["notified"] = prev.get("notified", [])
        try:
            with open(self.UPDATES_FILE, "w") as f:
                json.dump(res, f)
        except OSError:
            pass
        return res

    def _updates_loop(self):
        # First check a minute after start, then whenever the last one is a day old.
        if self._updates_stop.wait(60):
            return
        while not self._updates_stop.is_set():
            if self.settings.get("check_updates", True) and updates.due(self._updates_cached()):
                res = self._updates_run()
                new = [i for i in res["items"] if i["update"] and f"{i['id']}@{i['latest']}" not in res["notified"]]
                if new:
                    self._emit("pitwall_toast", "Update available: " + ", ".join(i["name"] for i in new) + ". See Pitwall, Updates.")
                    res["notified"] = res["notified"] + [f"{i['id']}@{i['latest']}" for i in new]
                    try:
                        with open(self.UPDATES_FILE, "w") as f:
                            json.dump(res, f)
                    except OSError:
                        pass
            self._updates_stop.wait(3600)

    async def updates_status(self, force: bool = False) -> dict:
        """Driver and bridge updates. force runs a fresh check; otherwise the last result."""
        res = await self._run(self._updates_run) if force else (self._updates_cached() or {"checked": 0, "items": [], "available": []})
        # Reflect installs made since the last check.
        st = self.drivers.state()
        res["items"] = [i for i in res.get("items", []) if i["kind"] != "driver" or i["id"] in st]
        for i in res["items"]:
            if i["kind"] == "driver" and i.get("latest") and (st[i["id"]].get("sha") or "").startswith(i["latest"]):
                i["update"], i["current"] = False, st[i["id"]].get("commit")
            if i["kind"] == "bridge" and i.get("latest") and bridge.installed_version(HOME) == i["latest"]:
                i["update"], i["current"] = False, i["latest"]
        res["available"] = [i["id"] for i in res["items"] if i["update"]]
        res["enabled"] = bool(self.settings.get("check_updates", True))
        res["has_anything"] = bool(st) or bridge.installed(HOME)
        return res

    # ===================================================== health / perf
    async def health_check(self) -> list:
        game = None
        if self.current_app:
            game = self.compat.find(self.current_app["appid"], self.current_app["name"])
        w = await self._run(self._wheel)
        return await self._run(lambda: health.check(self.hub, w, game, MANGOHUD_DIR))

    async def benchmark_options(self, seconds: int = 90) -> str:
        # The backend runs as root but the game runs as the desktop user, who
        # must be able to write logs here.
        os.makedirs(MANGOHUD_DIR, exist_ok=True)
        _chown_to_user(os.path.dirname(MANGOHUD_DIR), MANGOHUD_DIR)
        return perf.benchmark_launch_options(MANGOHUD_DIR, seconds)

    async def perf_analyse(self, appid: str = "", name: str = "") -> dict:
        g = self.compat.find(appid or None, name or None) if (appid or name) else None
        hints = (g or {}).get("perf_hints")
        return await self._run(perf.analyse_latest, MANGOHUD_DIR, float(self.settings["target_fps"]), hints)

    # ============================================================ engineer
    async def debrief(self) -> dict:
        summary = engineer.build_summary(self.hub.session_summary())
        out = {"summary": summary, "lines": engineer.offline_debrief(summary), "claude": None, "error": None}
        key = self.settings.get("anthropic_api_key")
        if key and summary.get("laps"):
            try:
                out["claude"] = await self._run(engineer.claude_debrief, summary, key)
            except Exception as e:  # network, auth, etc.
                out["error"] = f"Claude debrief unavailable: {e}"
        return out

    # ============================================================ buttons
    def _devices(self) -> dict:
        return self.buttons.snapshot_devices()

    def _nav_map(self, devices: dict) -> dict:
        m = dict(self.settings.get("nav_map") or {})
        if not m and devices:
            m = vpad.default_map(next(iter(devices.values())))
        return m

    def _game_layout(self, devices: dict) -> dict:
        keep = self.settings.get("game_layout") or {}
        # The Steam controls stay free in the automatic part where possible, so
        # one button doesn't mean two different things.
        return gamebinds.auto_layout(devices, keep)

    def _apply_nav(self):
        devices = self._devices()
        self.nav.configure(self.settings.get("nav_enabled", True), self._nav_map(devices))

    def _on_button(self, control: str, pressed: bool, dev):
        if not (self._learn_target and pressed):     # a press being learned doesn't also click in Steam
            self.nav.on_button(control, pressed)
        if not pressed:
            return
        devices = self._devices()
        if self.current_app:
            does = gamebinds.action_for(self._game_layout(devices), control)
        else:
            a = next((a for a, c in self._nav_map(devices).items() if c == control), None)
            does = vpad.ACTION_LABELS.get(a) if a and self.nav.active else None
        self.hub.button_hint = {"button": buttons.control_label(control, devices), "does": does,
                                "t": __import__("time").time()}

    def _on_devices(self):
        # A wheel appeared or went away: refresh the Steam layout and BeamNG.
        self._apply_nav()
        try:
            self._beamng_sync()
        except Exception:
            decky.logger.exception("BeamNG binding failed")

    def _beamng_sync(self) -> dict | None:
        if not self.settings.get("beamng_auto", True):
            return None
        devices = self._devices()
        if not devices:
            return None
        if self.current_app and self.current_app["appid"] == gamebinds.BEAMNG_APPID:
            return {"ok": False, "error": "Close BeamNG.drive first; it saves its controls on exit."}
        r = gamebinds.beamng_apply(HOME, self._game_layout(devices), devices)
        if r.get("written"):
            _chown_tree_to_user(r["written"])
        return r

    async def buttons_status(self) -> dict:
        snap = self.buttons.snapshot()
        devices = {d["id"]: d for d in snap["devices"]}
        label = lambda c: buttons.control_label(c, devices) if c else None
        nav_map = self._nav_map(devices)
        layout = self._game_layout(devices)
        in_game = self.current_app is not None
        recent = []
        for r in snap["recent"][:6]:
            c = r["control"]
            steam = next((vpad.ACTION_LABELS[a] for a, v in nav_map.items() if v == c), None)
            recent.append({**r, "steam": steam, "game": gamebinds.action_for(layout, c)})
        user_set = self.settings.get("game_layout") or {}
        return {
            "devices": [{"id": d["id"], "name": d["name"], "buttons": len(d["buttons"]), "hats": len(d["hats"])}
                        for d in snap["devices"]],
            "pressed": [label(c) for c in snap["pressed"]],
            "recent": recent,
            "in_game": in_game,
            "game": (self.current_app or {}).get("name"),
            "uinput": os.path.exists("/dev/uinput"),
            "nav": {"enabled": bool(self.settings.get("nav_enabled", True)), "active": self.nav.active,
                    "error": self.nav.error, "custom": bool(self.settings.get("nav_map")),
                    "rows": [{"action": a, "label": l, "control": nav_map.get(a), "button": label(nav_map.get(a))}
                             for a, l in vpad.ACTIONS]},
            "layout": {"rows": [{**r, "auto": bool(r["control"]) and r["action"] not in user_set}
                                for r in gamebinds.describe(layout, devices, buttons.control_label)],
                       "paddles": bool(layout.get("shift_up") and layout.get("shift_down"))},
            "beamng": {**(await self._run(gamebinds.beamng_status, HOME)), "auto": bool(self.settings.get("beamng_auto", True))},
            "learning": self._learn_target,
        }

    async def buttons_learn(self, kind: str, action: str) -> dict:
        """Arm: the next wheel button pressed becomes this action."""
        if kind == "nav" and action not in vpad.ACTION_LABELS or kind == "game" and action not in gamebinds.LABELS \
                or kind not in ("nav", "game"):
            return {"ok": False}
        self._learn_target = {"kind": kind, "action": action}
        self.buttons.learn(15)
        return {"ok": True}

    async def buttons_learned(self) -> dict:
        r = self.buttons.learned()
        t = self._learn_target
        if r["state"] in ("timeout", "idle"):
            self._learn_target = None
        if r["state"] != "done" or not t:
            return r
        self._learn_target = None
        devices = self._devices()
        key = "nav_map" if t["kind"] == "nav" else "game_layout"
        m = dict(self._nav_map(devices) if key == "nav_map" else (self.settings.get(key) or {}))
        for a, c in list(m.items()):        # one button, one job
            if c == r["control"]:
                del m[a]
        m[t["action"]] = r["control"]
        self.settings[key] = m
        _save(self.settings)
        if key == "nav_map":
            self._apply_nav()
        else:
            r["beamng"] = await self._run(self._beamng_sync)
        return r

    async def buttons_cancel_learn(self):
        self._learn_target = None
        self.buttons.learned()

    async def buttons_reset(self, kind: str) -> dict:
        key = {"nav": "nav_map", "game": "game_layout"}.get(kind)
        if not key:
            return {"ok": False}
        self.settings[key] = {}
        _save(self.settings)
        if key == "nav_map":
            self._apply_nav()
        else:
            await self._run(self._beamng_sync)
        return {"ok": True}

    async def beamng_bind(self, enable: bool) -> dict:
        self.settings["beamng_auto"] = bool(enable)
        _save(self.settings)
        if enable:
            return await self._run(self._beamng_sync) or {"ok": False, "error": "No wheel buttons found yet."}
        removed = await self._run(gamebinds.beamng_remove, HOME)
        return {"ok": True, "removed": removed}

    # ============================================================ graphics
    async def _graphics_game(self, appid: str, name: str, running: bool, game) -> dict:
        t = self.tuner
        if running:
            if appid not in t.games and self.settings.get("auto_graphics", True) and game:
                e = await self._run(t.enroll, appid, name)
                self._emit("pitwall_toast", f"Pitwall will tune {e['name']}'s graphics for this machine from its next start. "
                           "It measures while you drive and adjusts after you quit.")
            if appid in t.games:
                await self._run(t.started, appid)
                return {"enrolled": True}
            return {"enrolled": False}
        r = await self._run(t.finished, appid, float(self.settings["target_fps"]))
        if r and r.get("message"):
            self._emit("pitwall_toast", r["message"])
        return {"enrolled": appid in t.games, **(r or {})}

    async def graphics_status(self) -> dict:
        return {"device": self.device_kind, "target_fps": self.settings["target_fps"],
                "auto": bool(self.settings.get("auto_graphics", True)), "games": self.tuner.status(),
                "tiers": [{"id": k, "label": graphics.TIER_LABELS[k]} for k in graphics.TIERS]}

    async def graphics_launch_options(self, appid: str, current: str, enable: bool) -> str:
        """The game's launch options with Pitwall's frame cap and quiet measuring
        added (or taken out), everything else kept."""
        folder = graphics.log_dir(MANGOHUD_DIR, str(appid))
        if enable:
            os.makedirs(folder, exist_ok=True)
            _chown_to_user(os.path.dirname(MANGOHUD_DIR), MANGOHUD_DIR, os.path.dirname(folder), folder)
        return graphics.launch_options(current or "", bool(enable), int(self.settings["target_fps"]), folder)

    async def graphics_enroll(self, appid: str, name: str) -> dict:
        e = await self._run(self.tuner.enroll, str(appid), name)
        return {"ok": True, "tier": e["tier"]}

    async def graphics_forget(self, appid: str) -> bool:
        return await self._run(self.tuner.forget, str(appid))

    async def graphics_set_tier(self, appid: str, tier: str) -> dict:
        e = await self._run(self.tuner.set_tier, str(appid), tier)
        return {"ok": e is not None, "write": (e or {}).get("write")}

    # ============================================================ settings
    async def get_settings(self) -> dict:
        s = dict(self.settings)
        s["anthropic_api_key"] = bool(s.get("anthropic_api_key"))   # never send the key to the UI
        return {k: s[k] for k in ("auto_apply", "target_fps", "units", "dashboard_port", "anthropic_api_key", "rev_lights", "setup_done", "check_updates", "nav_enabled", "auto_graphics")}

    # Settings the UI may change, each with a check on the value.
    SETTING_CHECKS = {
        "target_fps": lambda v: isinstance(v, int) and not isinstance(v, bool) and 20 <= v <= 240,
        "units": lambda v: v in ("kmh", "mph"),
        "anthropic_api_key": lambda v: isinstance(v, str) and len(v) < 400,
        "rev_lights": lambda v: isinstance(v, bool),
        "check_updates": lambda v: isinstance(v, bool),
        "nav_enabled": lambda v: isinstance(v, bool),
        "auto_graphics": lambda v: isinstance(v, bool),
    }

    async def set_setting(self, key: str, value):
        check = self.SETTING_CHECKS.get(key)
        if check is None:
            return False
        if key == "target_fps" and isinstance(value, float) and value.is_integer():
            value = int(value)
        if key == "anthropic_api_key" and isinstance(value, str):
            value = value.strip()
        if not check(value):
            return False
        self.settings[key] = value
        _save(self.settings)
        if key == "rev_lights":
            self._apply_rev_lights()
        if key == "nav_enabled":
            self._apply_nav()
        return True

    def _apply_rev_lights(self):
        want = bool(self.settings.get("rev_lights"))
        if want and not (self.rev_lights and self.rev_lights.is_alive()):
            self.rev_lights = RevLights(self.hub, self._wheel)
            self.rev_lights.start()
        elif not want and self.rev_lights:
            self.rev_lights.stop()
            self.rev_lights = None

    # ============================================================ lifecycle
    async def _main(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.settings = _load()
        self.current_app = None
        self.wheel = None
        self.wheel_lock = threading.Lock()
        self.ffb_undo_stack = []
        self.rev_lights = None
        self.hub = Hub(os.path.join(DATA_DIR, "laps.sqlite"), ports=self.settings.get("ports"), logger=decky.logger)
        self.hub.start()
        self.loop = asyncio.get_running_loop()
        self.downloads = diagnostics.DownloadTokens()
        self.hub.car_listeners.append(self._on_car_change)
        self.dashboard = Dashboard(self.hub, int(self.settings["dashboard_port"]), self.downloads)
        self.dashboard.start()
        self.compat = compat_mod.Compat(HOME, DATA_DIR)
        self._apply_rev_lights()
        self.drivers = drivers.Installer(os.path.join(SETTINGS_DIR, "drivers.json"), os.path.join(DATA_DIR, "driver-build"))
        stale = [drivers.DRIVERS[d]["name"] for d, r in self.drivers.status()["installed"].items() if r["stale"]]
        if stale:
            # A SteamOS update replaced the kernel and removed the driver; say so once the UI is up.
            self.loop.call_later(20, self._emit, "pitwall_toast",
                                 f"A SteamOS update removed {', '.join(stale)}. Reinstall it in Pitwall, Wheel, Force feedback.")
        self._updates_stop = threading.Event()
        threading.Thread(target=self._updates_loop, daemon=True).start()
        try:
            self.device_kind = device.detect()["kind"]
        except Exception:
            self.device_kind = "pc"
        self.tuner = graphics.Tuner(os.path.join(SETTINGS_DIR, "graphics.json"), HOME, MANGOHUD_DIR, self.device_kind,
                                    self.compat.find, lambda a: compat_mod.prefix_path(HOME, int(a)))
        self._learn_target = None
        self.nav = vpad.NavBridge(log=decky.logger)
        self.buttons = buttons.ButtonWatcher(lambda: [w["event"] for w in health.input_wheels()])
        self.buttons.listeners.append(self._on_button)
        self.buttons.device_listeners.append(self._on_devices)
        self.buttons.start()
        decky.logger.info("Pitwall started; dashboard at %s", self.dashboard.url)

    async def _unload(self):
        if getattr(self, "_updates_stop", None):
            self._updates_stop.set()
        if getattr(self, "buttons", None):
            self.buttons.stop()
        if getattr(self, "nav", None):
            self.nav.close()
        if getattr(self, "rev_lights", None):
            self.rev_lights.stop()
        if getattr(self, "hub", None):
            self.hub.stop()
        if getattr(self, "dashboard", None):
            self.dashboard.stop()
        if getattr(self, "wheel", None):
            self.wheel.close()

    async def _uninstall(self):
        """Undo Pitwall's system changes: the wheel detection udev rule and any
        force feedback drivers it installed. The telemetry bridge in
        ~/.local/share/pitwall stays, because games' launch options may still
        use it; Pitwall's settings and laps stay, as with any Decky plugin."""
        try:
            health.remove_joystick_fix()
        except Exception:
            decky.logger.exception("Removing the wheel detection rule failed")
        try:
            inst = getattr(self, "drivers", None) or drivers.Installer(
                os.path.join(SETTINGS_DIR, "drivers.json"), os.path.join(DATA_DIR, "driver-build"))
            removed = await self._run(inst.remove_all)
            if removed:
                decky.logger.info("Removed drivers on uninstall: %s", removed)
        except Exception:
            decky.logger.exception("Removing installed drivers failed")
