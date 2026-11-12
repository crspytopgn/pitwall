"""Per-game graphics tuning, measured on your machine.

Each tuned game sits on a quality level: Max, High, Balanced or Performance.
Pitwall starts it at the level that fits the device (the Steam Machine gets
more than a Steam Deck), caps the frame rate at your target so it stays
steady, and logs frame times quietly with MangoHud while you drive. When the
game closes, Pitwall reads the log and moves the level:

- below target, or bad 1% lows: one level down
- on target with the GPU mostly idle: one level up, unless that level was
  already too slow on this machine (so it never flip-flops)

Where Pitwall knows a game's settings file it changes the settings itself
(Assetto Corsa's video.ini, only keys that are already there, with a
backup). For other games it tells you which of the game's own presets to
pick, and the frame cap and measuring still work.
"""

from __future__ import annotations

import configparser
import glob
import io
import json
import os
import re
import shutil
import time

from . import perf

TIERS = ["max", "high", "balanced", "performance"]
TIER_LABELS = {"max": "Max", "high": "High", "balanced": "Balanced", "performance": "Performance"}

# Where each device starts, per game weight. "light" games are older or
# lighter engines; "heavy" are Unreal/modern engines.
START = {
    "steam_machine": {"light": "max", "medium": "high", "heavy": "balanced"},
    "pc": {"light": "high", "medium": "high", "heavy": "balanced"},
    "steam_deck": {"light": "balanced", "medium": "performance", "heavy": "performance"},
}

# Per game: weight, and the game's own preset names from best to lowest,
# matched to Max..Performance. None: no single preset; general advice.
GAMES = {
    "ac": {"weight": "light", "writer": "ac"},
    "acc": {"weight": "heavy", "presets": ["Epic", "High", "Mid", "Low"]},
    "ac_evo": {"weight": "heavy"},
    "ac_rally": {"weight": "heavy"},
    "ams2": {"weight": "medium"},
    "pc2": {"weight": "medium"},
    "rf2": {"weight": "medium"},
    "lmu": {"weight": "heavy"},
    "raceroom": {"weight": "light"},
    "beamng": {"weight": "heavy", "presets": ["Ultra", "High", "Normal", "Low"]},
    "dr2": {"weight": "medium", "presets": ["Ultra", "High", "Medium", "Low"]},
    "dirt_rally": {"weight": "light", "presets": ["Ultra", "High", "Medium", "Low"]},
    "dirt_4": {"weight": "medium", "presets": ["Ultra", "High", "Medium", "Low"]},
    "fh4": {"weight": "medium", "presets": ["Ultra", "High", "Medium", "Low"]},
    "fh5": {"weight": "heavy", "presets": ["Ultra", "High", "Medium", "Low"]},
    "fh6": {"weight": "heavy", "presets": ["Ultra", "High", "Medium", "Low"]},
    "fm": {"weight": "heavy", "presets": ["Ultra", "High", "Medium", "Low"]},
    "f1_2021": {"weight": "medium", "presets": ["Ultra High", "High", "Medium", "Low"]},
    "f1_22": {"weight": "medium", "presets": ["Ultra High", "High", "Medium", "Low"]},
    "f1_23": {"weight": "heavy", "presets": ["Ultra High", "High", "Medium", "Low"]},
    "f1_24": {"weight": "heavy", "presets": ["Ultra High", "High", "Medium", "Low"]},
    "f1_25": {"weight": "heavy", "presets": ["Ultra High", "High", "Medium", "Low"]},
    "ets2": {"weight": "medium", "presets": ["Ultra", "High", "Medium", "Low"]},
    "ats": {"weight": "medium", "presets": ["Ultra", "High", "Medium", "Low"]},
    "lfs": {"weight": "light"},
    "iracing": {"weight": "medium"},
}

# Render resolution per level, for a 4K TV; the Steam Machine upscales the rest.
RENDER = {"max": None, "high": None, "balanced": (2560, 1440), "performance": (1920, 1080)}

GENERAL = {
    "max": "Use the game's highest preset.",
    "high": "Use the game's high preset.",
    "balanced": "Use the game's medium preset, or high with shadows and reflections one step lower. Render at 1440p if the game lets you choose.",
    "performance": "Use the game's low preset, mirrors and reflections low, fewer AI cars. Render at 1080p if the game lets you choose.",
}

LOG_DELAY = 120      # start measuring 2 minutes in, past menus and loading
LOG_SECONDS = 180


def start_tier(game_id: str, device_kind: str) -> str:
    g = GAMES.get(game_id, {"weight": "medium"})
    return START.get(device_kind, START["pc"])[g["weight"]]


def advice(game_id: str | None, tier: str) -> str:
    g = GAMES.get(game_id or "", {})
    if g.get("writer"):
        return f"Pitwall sets this game's graphics to {TIER_LABELS[tier]} itself."
    if g.get("presets"):
        p = g["presets"][TIERS.index(tier)]
        extra = {"balanced": " Render at 1440p if the game lets you choose.",
                 "performance": " Mirrors and reflections low, fewer AI cars."}.get(tier, "")
        return f"In the game's graphics menu, choose the {p} preset.{extra}"
    return GENERAL[tier]


# ------------------------------------------------------------- launch options
def log_dir(base: str, appid: str) -> str:
    return os.path.join(base, "tune", str(appid))


def mangohud_config(fps: int, folder: str) -> str:
    # no_display: measure without drawing an overlay on top of the game.
    # autostart_log is a delay in seconds.
    return f"no_display,fps_limit={int(fps)},autostart_log={LOG_DELAY},log_duration={LOG_SECONDS},output_folder={folder}"


def launch_options(current: str, enable: bool, fps: int, folder: str) -> str:
    """Add or remove Pitwall's frame cap and quiet logging, keeping the rest."""
    from .health import env_launch_options
    cur = env_launch_options(current, "MANGOHUD_CONFIG", "", False)
    cur = env_launch_options(cur, "MANGOHUD", "", False)
    if not enable:
        return cur
    cur = env_launch_options(cur, "MANGOHUD_CONFIG", mangohud_config(fps, folder), True)
    return env_launch_options(cur, "MANGOHUD", "1", True)


def has_launch_options(current: str) -> bool:
    return bool(re.search(r"MANGOHUD_CONFIG=\S*no_display\S*output_folder=\S*/tune/", current or ""))


# ------------------------------------------------------------- measuring
def read_gpu_load(path: str) -> float | None:
    """Median GPU load (%) from a MangoHud log, if it recorded one."""
    import csv
    import statistics
    try:
        with open(path, newline="", errors="ignore") as f:
            rows = list(csv.reader(f))
    except OSError:
        return None
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "fps":
            header = [h.strip().lower() for h in row]
            if "gpu_load" not in header:
                return None
            col = header.index("gpu_load")
            vals = []
            for r in rows[i + 1:]:
                try:
                    vals.append(float(r[col]))
                except (ValueError, IndexError):
                    continue
            return statistics.median(vals) if vals else None
    return None


def decide(entry: dict, result: dict, target: float, gpu_load: float | None) -> tuple[str, str]:
    """Next level and what to tell you. Pure: entry is not changed."""
    tier = entry["tier"]
    i = TIERS.index(tier)
    floor = entry.get("too_slow")          # lowest level that was too slow here; never climb back to it
    v, avg, low1 = result["verdict"], result["avg_fps"], result["low1_fps"]
    if v == "too_slow" or (v == "stutters" and low1 < target * 0.85):
        if i + 1 < len(TIERS):
            return TIERS[i + 1], f"ran at {avg:.0f} FPS (1% low {low1:.0f}) against {target:.0f}. Graphics lowered to {TIER_LABELS[TIERS[i + 1]]} for next time."
        return tier, f"ran at {avg:.0f} FPS against {target:.0f} even on Performance. Try a lower target FPS, fewer AI cars, or a lower resolution."
    if v == "stutters":
        return tier, f"averaged {avg:.0f} FPS with some stutters. That's usually shaders compiling the first time on a track, so the level stays at {TIER_LABELS[tier]}."
    # On target: is there room for more?
    if i > 0 and (gpu_load is not None and gpu_load < 70) and (floor is None or TIERS.index(floor) < i - 1):
        return TIERS[i - 1], f"held {target:.0f} FPS with the GPU at {gpu_load:.0f}%. Graphics raised to {TIER_LABELS[TIERS[i - 1]]} for next time."
    return tier, f"held {target:.0f} FPS on {TIER_LABELS[tier]}. Staying there."


def newest_log(folder: str, since: float, seen: str | None = None) -> str | None:
    logs = [p for p in glob.glob(os.path.join(folder, "*.csv")) if not p.endswith("_summary.csv")]
    logs = [p for p in logs if os.path.getmtime(p) >= since and os.path.basename(p) != seen]
    return max(logs, key=os.path.getmtime) if logs else None


# ------------------------------------------------------------- Assetto Corsa
AC_LEVELS = {
    #            AA  aniso shadows mirrorHQ mirror cube faces cubeFar motionBlur dof
    "max":         (4, 16, 4096, 1, 1024, 2048, 3, 2000, 0, None),
    "high":        (4, 16, 2048, 1, 1024, 1024, 2, 1000, 0, None),
    "balanced":    (2, 8, 2048, 0, 512, 512, 1, 500, 0, 0),
    "performance": (1, 4, 1024, 0, 512, 256, 1, 250, 0, 0),
}


def ac_video_ini(prefix: str) -> str:
    return os.path.join(prefix, "drive_c", "users", "steamuser", "Documents", "Assetto Corsa", "cfg", "video.ini")


def _ini_set(text: str, changes: dict[tuple[str, str], object]) -> tuple[str, list[str]]:
    """Change KEY=value lines that already exist under [SECTION]; nothing is
    added, comments and order are kept."""
    out, section, done = [], None, []
    for line in text.splitlines(keepends=True):
        m = re.match(r"\s*\[([^\]]+)\]", line)
        if m:
            section = m.group(1).strip().upper()
        else:
            k = re.match(r"(\s*)([A-Za-z0-9_]+)(\s*=\s*)([^\r\n;]*)(.*?)(\r?\n)?$", line)
            if k and section and (section, k.group(2).upper()) in changes:
                val = changes[(section, k.group(2).upper())]
                if str(val) != k.group(4).strip():
                    done.append(f"{section}/{k.group(2)}={val}")
                raw = k.group(4)
                line = f"{k.group(1)}{k.group(2)}{k.group(3)}{val}{raw[len(raw.rstrip()):]}{k.group(5)}{k.group(6) or ''}"
        out.append(line)
    return "".join(out), done


def ac_apply(prefix: str, tier: str) -> dict:
    path = ac_video_ini(prefix)
    try:
        with open(path, errors="replace") as f:
            text = f.read()
    except OSError:
        return {"ok": False, "message": "Assetto Corsa's video.ini wasn't found. Start the game once, then Pitwall can tune it."}
    aa, aniso, shadow, mhq, msize, csize, faces, far, blur, dof = AC_LEVELS[tier]
    ch = {("VIDEO", "AASAMPLES"): aa, ("VIDEO", "ANISOTROPIC"): aniso, ("VIDEO", "SHADOW_MAP_SIZE"): shadow,
          ("MIRROR", "HQ"): mhq, ("MIRROR", "SIZE"): msize,
          ("CUBEMAP", "SIZE"): csize, ("CUBEMAP", "FACES_PER_FRAME"): faces, ("CUBEMAP", "FARPLANE"): far,
          ("EFFECTS", "MOTION_BLUR"): blur}
    if dof is not None:
        ch[("POST_PROCESS", "DOF")] = dof
    res = RENDER[tier]
    if res:
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            cp.read_file(io.StringIO(text))
            w, h = int(cp.get("VIDEO", "WIDTH")), int(cp.get("VIDEO", "HEIGHT"))
            if w > res[0]:           # only ever lower the resolution
                ch[("VIDEO", "WIDTH")], ch[("VIDEO", "HEIGHT")] = res
        except (configparser.Error, ValueError):
            pass
    new, done = _ini_set(text, ch)
    if done:
        backup = path + ".pitwall-backup"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(new)
        os.replace(tmp, path)
    return {"ok": True, "changed": done, "path": path}


def ac_restore(prefix: str) -> bool:
    path = ac_video_ini(prefix)
    if os.path.exists(path + ".pitwall-backup"):
        os.replace(path + ".pitwall-backup", path)
        return True
    return False


# ------------------------------------------------------------- state
class Tuner:
    def __init__(self, path: str, home: str, mangohud_base: str, device_kind: str, find_game, prefix_for):
        self.path, self.home, self.base, self.device = path, home, mangohud_base, device_kind
        self.find_game = find_game          # (appid, name) -> compat entry or None
        self.prefix_for = prefix_for        # appid -> Proton prefix path or None
        self.games: dict = self._load()

    def _load(self) -> dict:
        try:
            with open(self.path) as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.games, f, indent=2)
        os.replace(tmp, self.path)

    def _write(self, appid: str, entry: dict) -> dict | None:
        if GAMES.get(entry.get("game") or "", {}).get("writer") == "ac":
            prefix = self.prefix_for(appid)
            if prefix:
                return ac_apply(prefix, entry["tier"])
            return {"ok": False, "message": "Assetto Corsa's Proton prefix wasn't found. Start the game once."}
        return None

    def enroll(self, appid: str, name: str) -> dict:
        appid = str(appid)
        if appid in self.games:
            return self.games[appid]
        g = self.find_game(appid, name)
        gid = g["id"] if g else None
        entry = {"name": (g or {}).get("name") or name or f"App {appid}", "game": gid,
                 "tier": start_tier(gid or "", self.device), "too_slow": None, "runs": [], "started": None}
        self.games[appid] = entry
        entry["write"] = self._write(appid, entry)
        self._save()
        return entry

    def forget(self, appid: str) -> bool:
        entry = self.games.pop(str(appid), None)
        if entry and GAMES.get(entry.get("game") or "", {}).get("writer") == "ac":
            p = self.prefix_for(str(appid))
            if p:
                ac_restore(p)
        self._save()
        return entry is not None

    def set_tier(self, appid: str, tier: str) -> dict | None:
        e = self.games.get(str(appid))
        if not e or tier not in TIERS:
            return None
        e["tier"], e["too_slow"] = tier, None       # your choice resets what Pitwall learned
        e["write"] = self._write(str(appid), e)
        self._save()
        return e

    def started(self, appid: str):
        e = self.games.get(str(appid))
        if e:
            e["started"] = time.time()
            self._save()

    def finished(self, appid: str, target: float) -> dict | None:
        """After a session: read the log, move the level, write the settings."""
        e = self.games.get(str(appid))
        if not e or not e.get("started"):
            return None
        since, e["started"] = e["started"], None
        path = newest_log(log_dir(self.base, appid), since, e.get("seen"))
        if not path:
            self._save()
            return {"changed": False, "message": None}
        res = perf.analyse(perf.read_frametimes(path), target)
        if not res.get("ok"):
            self._save()
            return {"changed": False, "message": None}       # too short a session to judge
        e["seen"] = os.path.basename(path)
        gpu = read_gpu_load(path)
        old = e["tier"]
        new, msg = decide(e, res, target, gpu)
        if TIERS.index(new) > TIERS.index(old):
            e["too_slow"] = old if e.get("too_slow") is None or TIERS.index(old) > TIERS.index(e["too_slow"]) else e["too_slow"]
        e["tier"] = new
        e["runs"] = ([{"t": int(time.time()), "tier": old, "avg": res["avg_fps"], "low1": res["low1_fps"],
                       "gpu": gpu, "verdict": res["verdict"]}] + e.get("runs", []))[:5]
        if new != old:
            e["write"] = self._write(str(appid), e)
        self._save()
        for p in glob.glob(os.path.join(log_dir(self.base, appid), "*.csv")):
            if os.path.getmtime(p) < since - 86400:
                os.remove(p)                 # keep a day of logs
        # Say something when the level moved, after the first measured run, or
        # when even the lowest level isn't enough; not after every session.
        speak = new != old or len(e["runs"]) == 1 or (res["verdict"] == "too_slow" and new == TIERS[-1])
        return {"changed": new != old, "tier": new, "message": f"{e['name']} {msg}" if speak else None}

    def status(self) -> list[dict]:
        out = []
        for appid, e in self.games.items():
            out.append({"appid": appid, "name": e["name"], "tier": e["tier"], "label": TIER_LABELS[e["tier"]],
                        "auto_settings": bool(GAMES.get(e.get("game") or "", {}).get("writer")),
                        "advice": advice(e.get("game"), e["tier"]), "last": (e.get("runs") or [None])[0],
                        "write_error": (e.get("write") or {}).get("message") if e.get("write") and not e["write"].get("ok") else None})
        return sorted(out, key=lambda x: x["name"].lower())
