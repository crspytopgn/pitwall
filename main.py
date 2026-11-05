"""Pitwall Decky backend: wires the pitwall package to the Quick Access UI."""

import asyncio
import json
import os
import sys

import decky  # provided by Decky Loader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "py_modules"))

from pitwall import compat as compat_mod  # noqa: E402
from pitwall import engineer, ffb, health, perf  # noqa: E402
from pitwall.dashboard import Dashboard  # noqa: E402
from pitwall.hub import Hub  # noqa: E402
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
    "target_fps": 60,
    "units": "kmh",
    "dashboard_port": 8090,
    "ports": {},                    # overrides for telemetry ports
    "anthropic_api_key": "",
}

PROFILE_EXCLUDE = {"ffb_enabled"}   # never let a profile silently switch FFB off


def _load() -> dict:
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **data}


def _chown_to_user(*paths):
    try:
        import pwd
        pw = pwd.getpwnam(decky.DECKY_USER)
        for p in paths:
            os.chown(p, pw.pw_uid, pw.pw_gid)
    except (KeyError, OSError, AttributeError):
        pass


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
        if self.wheel is None or not self.wheel.detect():
            if self.wheel:
                self.wheel.close()
            self.wheel = detect_wheel(decky.logger, os.environ.get("PITWALL_MOZA_TTY"))
        return self.wheel

    async def wheel_status(self) -> dict:
        w = await self._run(self._wheel)
        if not w:
            return {"connected": False, "error": "No supported wheel found (MOZA and Logitech are supported)."}
        return {"connected": True, "name": w.name, "brand": w.brand, "settings": w.settings(),
                "can_center": w.brand == "MOZA"}

    async def wheel_read(self):
        w = await self._run(self._wheel)
        return await self._run(w.read_all) if w else None

    async def wheel_set(self, key: str, value: float) -> bool:
        w = await self._run(self._wheel)
        return bool(w) and await self._run(w.write, {key: value})

    async def wheel_center(self) -> bool:
        w = await self._run(self._wheel)
        return bool(w) and await self._run(w.center)

    async def get_profiles(self) -> dict:
        s = self.settings
        return {"auto_apply": s["auto_apply"], "has_default": s["wheel_default"] is not None,
                "games": {k: v.get("name", k) for k, v in s["wheel_games"].items()}}

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
        else:
            self.settings["wheel_games"][str(appid)] = {"name": name, "settings": values}
        _save(self.settings)
        return True

    async def delete_profile(self, appid: str):
        if appid == "default":
            self.settings["wheel_default"] = None
        else:
            self.settings["wheel_games"].pop(str(appid), None)
        _save(self.settings)

    async def apply_profile(self, appid: str) -> bool:
        s = self.settings
        prof = s["wheel_default"] if appid == "default" else s["wheel_games"].get(str(appid))
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
        g = self.compat.find(appid, name)
        result["game"] = {"id": g["id"], "name": g["name"], "status": g["status"]} if g else None
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

    # ============================================================ settings
    async def get_settings(self) -> dict:
        s = dict(self.settings)
        s["anthropic_api_key"] = bool(s.get("anthropic_api_key"))   # never send the key to the UI
        return {k: s[k] for k in ("auto_apply", "target_fps", "units", "dashboard_port", "anthropic_api_key")}

    async def set_setting(self, key: str, value):
        if key not in ("target_fps", "units", "anthropic_api_key"):
            return False
        self.settings[key] = value
        _save(self.settings)
        return True

    # ============================================================ lifecycle
    async def _main(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.settings = _load()
        self.current_app = None
        self.wheel = None
        self.ffb_undo_stack = []
        self.hub = Hub(os.path.join(DATA_DIR, "laps.sqlite"), ports=self.settings.get("ports"), logger=decky.logger)
        self.hub.start()
        self.dashboard = Dashboard(self.hub, int(self.settings["dashboard_port"]))
        self.dashboard.start()
        self.compat = compat_mod.Compat(HOME, DATA_DIR)
        decky.logger.info("Pitwall started; dashboard at %s", self.dashboard.url)

    async def _unload(self):
        self.hub.stop()
        self.dashboard.stop()
        if self.wheel:
            self.wheel.close()

    async def _uninstall(self):
        pass
