"""Per-game graphics tuning, measured on your machine while you race.

Each tuned game sits on a quality level: Max, High, Balanced or Performance.
Pitwall starts it at the level that fits the device (the Steam Machine gets
more than a Steam Deck) and caps the frame rate at your target so it stays
steady. MangoHud logs frame times quietly for the whole session (no overlay),
and Pitwall keeps only the moments you were actually driving: on track, not
paused, moving, from the game's own telemetry. Menus, loading screens,
replays and the garage don't count. For a game without telemetry, the first
two minutes are skipped instead.

When the game closes, Pitwall judges those frames and moves the level:

- below target, or bad 1% lows: one level down
- on target with the GPU under 70% busy: one level up, unless that level
  was already too slow on this machine (so it settles instead of flip-flopping)

Then it changes the game's own settings for the new level, in every
settings file it recognises for that game (see gamesettings.py: Unreal
Engine, Codemasters EGO, Madness, SCS and Assetto Corsa formats). For a game
whose settings format isn't known, it tells you which of the game's presets
to pick; the frame cap and measuring work either way.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import statistics
import time

from . import gamesettings, perf

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

LOG_SECONDS = 5400        # the whole session, up to 90 minutes
LOG_INTERVAL_MS = 100     # one sample every 100 ms
WARMUP_S = 10             # skip the first seconds of each stint (pit exit, launch)
NO_TELEMETRY_SKIP_S = 120
MIN_RACING_S = 120        # this much driving before Pitwall judges a session


def start_tier(game_id: str, device_kind: str) -> str:
    g = GAMES.get(game_id, {"weight": "medium"})
    return START.get(device_kind, START["pc"])[g["weight"]]


def advice(game_id: str | None, tier: str, files: list | None = None) -> str:
    g = GAMES.get(game_id or "", {})
    if files:
        kinds = sorted({gamesettings.KIND_LABELS[k] for k, _ in files})
        rel = " Max is the settings you chose in the game; each level below turns detail down from there." \
            if any(k in ("madness", "scs") for k, _ in files) else ""
        return f"Pitwall changes {' and '.join(kinds)} itself, for the {TIER_LABELS[tier]} level.{rel}"
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
    return (f"no_display,fps_limit={int(fps)},autostart_log=1,log_duration={LOG_SECONDS},"
            f"log_interval={LOG_INTERVAL_MS},output_folder={folder}")


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
def read_rows(path: str, interval_s: float = LOG_INTERVAL_MS / 1000) -> list[tuple[float, float, float | None]]:
    """(seconds since the log started, frametime ms, GPU load % or None)."""
    try:
        with open(path, newline="", errors="ignore") as f:
            rows = list(csv.reader(f))
    except OSError:
        return []
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "fps":
            h = [x.strip().lower() for x in row]
            ft = h.index("frametime") if "frametime" in h else None
            el = h.index("elapsed") if "elapsed" in h else None
            gl = h.index("gpu_load") if "gpu_load" in h else None
            out = []
            for n, r in enumerate(rows[i + 1:]):
                try:
                    t = float(r[ft]) if ft is not None else 1000.0 / float(r[0])
                    off = float(r[el]) / 1e9 if el is not None else n * interval_s
                except (ValueError, IndexError, ZeroDivisionError):
                    continue
                g = None
                if gl is not None:
                    try:
                        g = float(r[gl])
                    except (ValueError, IndexError):
                        g = None
                if 0 < t < 1000:
                    out.append((off, t, g))
            return out
    return []


def racing_rows(path: str, windows: list[tuple[float, float]]) -> tuple[list, str]:
    """The log rows from while you were actually driving, and how they were picked.

    windows: wall-clock (start, end) stretches when telemetry said the car was
    on track and moving. Without any (a game with no telemetry), the first
    minutes are dropped instead."""
    rows = read_rows(path)
    if not rows:
        return [], "none"
    start = perf.log_start(path)
    if start is None:
        start = os.path.getmtime(path) - rows[-1][0]
    if windows:
        keep = [(a + WARMUP_S, b) for a, b in windows if b - a > WARMUP_S]
        picked = [r for r in rows if any(a <= start + r[0] <= b for a, b in keep)]
        return picked, "telemetry"
    return [r for r in rows if r[0] >= NO_TELEMETRY_SKIP_S], "time"


def seconds_of(rows: list, interval_s: float = LOG_INTERVAL_MS / 1000) -> float:
    if len(rows) < 2:
        return 0.0
    gaps = [b[0] - a[0] for a, b in zip(rows, rows[1:])]
    return sum(g for g in gaps if g <= 1.0) + interval_s


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
    """The log written during this session (MangoHud writes it when the game closes)."""
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
    return os.path.join(gamesettings.user_dir(prefix), "Documents", "Assetto Corsa", "cfg", "video.ini")


def _ini_set(text: str, changes: dict[tuple[str, str], object]) -> tuple[str, list[str]]:
    """Change KEY=value lines that already exist under [SECTION]; nothing is
    added, comments and order are kept."""
    out, section, done = [], None, []
    for line in text.splitlines(keepends=True):
        m = re.match(r"\s*\[([^\]]+)\]", line)
        if m:
            section = m.group(1).strip().upper()
        else:
            k = re.match(r"(\s*)([A-Za-z0-9_.]+)(\s*=\s*)([^\r\n;]*)(.*?)(\r?\n)?$", line)
            if k and section and (section, k.group(2).upper()) in changes:
                val = changes[(section, k.group(2).upper())]
                raw = k.group(4)
                if str(val) != raw.strip():
                    done.append(f"{section}/{k.group(2)}={val}")
                line = f"{k.group(1)}{k.group(2)}{k.group(3)}{val}{raw[len(raw.rstrip()):]}{k.group(5)}{k.group(6) or ''}"
        out.append(line)
    return "".join(out), done


def _ini_get(text: str, section: str, key: str) -> str | None:
    sec = None
    for line in text.splitlines():
        m = re.match(r"\s*\[([^\]]+)\]", line)
        if m:
            sec = m.group(1).strip().upper()
            continue
        k = re.match(r"\s*([A-Za-z0-9_.]+)\s*=\s*([^\r\n;]*)", line)
        if k and sec == section.upper() and k.group(1).upper() == key.upper():
            return k.group(2).strip()
    return None


def ac_writer(current: str, base: str, tier: str) -> tuple[str, list[str]]:
    aa, aniso, shadow, mhq, msize, csize, faces, far, blur, dof = AC_LEVELS[tier]
    ch = {("VIDEO", "AASAMPLES"): aa, ("VIDEO", "ANISOTROPIC"): aniso, ("VIDEO", "SHADOW_MAP_SIZE"): shadow,
          ("MIRROR", "HQ"): mhq, ("MIRROR", "SIZE"): msize,
          ("CUBEMAP", "SIZE"): csize, ("CUBEMAP", "FACES_PER_FRAME"): faces, ("CUBEMAP", "FARPLANE"): far,
          ("EFFECTS", "MOTION_BLUR"): blur}
    if dof is not None:
        ch[("POST_PROCESS", "DOF")] = dof
    try:
        w, h = int(_ini_get(base, "VIDEO", "WIDTH") or 0), int(_ini_get(base, "VIDEO", "HEIGHT") or 0)
    except ValueError:
        w = h = 0
    if w and h:
        res = gamesettings._lower_res(w, h, tier) or (w, h)       # only ever lower than yours
        ch[("VIDEO", "WIDTH")], ch[("VIDEO", "HEIGHT")] = res
    return _ini_set(current, ch)


gamesettings.WRITERS["ac"] = ac_writer


def ac_apply(prefix: str, tier: str) -> dict:
    path = ac_video_ini(prefix)
    if not os.path.isfile(path):
        return {"ok": False, "message": "Assetto Corsa's video.ini wasn't found. Start the game once, then Pitwall can tune it."}
    return gamesettings.apply("ac", path, tier)


def ac_restore(prefix: str) -> bool:
    return gamesettings.restore(ac_video_ini(prefix))


# ------------------------------------------------------------- state
class Tuner:
    def __init__(self, path: str, home: str, mangohud_base: str, device_kind: str, find_game, prefix_for,
                 on_written=None):
        self.path, self.home, self.base, self.device = path, home, mangohud_base, device_kind
        self.find_game = find_game          # (appid, name) -> compat entry or None
        self.prefix_for = prefix_for        # appid -> Proton prefix path or None
        self.on_written = on_written        # called with the paths written (to give them back to you)
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

    def files(self, appid: str, entry: dict) -> list[tuple[str, str]]:
        try:
            prefix = self.prefix_for(appid)
        except Exception:
            prefix = None
        if prefix and not os.path.isdir(prefix):
            prefix = None
        return gamesettings.find(prefix, self.home, entry.get("game"))

    def _write(self, appid: str, entry: dict, running: bool = False) -> dict | None:
        """Change the game's settings files for its level, or remember to once
        the game has closed (it would overwrite them on exit)."""
        if running:
            entry["pending"] = True
            return entry.get("write")
        entry["pending"] = False
        files = self.files(appid, entry)
        if not files:
            if GAMES.get(entry.get("game") or "", {}).get("writer") == "ac":
                return {"ok": False, "message": "Assetto Corsa's video.ini wasn't found. Start the game once, then Pitwall can tune it."}
            return None
        changed, errors, written = [], [], []
        for kind, path in files:
            r = gamesettings.apply(kind, path, entry["tier"])
            if r.get("ok"):
                changed += r["changed"]
                written += [path] + gamesettings.sidecars(path)
            else:
                errors.append(r.get("message"))
        if written and self.on_written:
            try:
                self.on_written(written)
            except Exception:
                pass
        if errors:
            return {"ok": False, "message": "; ".join(e for e in errors if e)}
        return {"ok": True, "changed": changed, "files": [p for _, p in files]}

    def enroll(self, appid: str, name: str, running: bool = False) -> dict:
        appid = str(appid)
        if appid in self.games:
            return self.games[appid]
        g = self.find_game(appid, name)
        gid = g["id"] if g else None
        entry = {"name": (g or {}).get("name") or name or f"App {appid}", "game": gid,
                 "tier": start_tier(gid or "", self.device), "too_slow": None, "runs": [], "started": None}
        self.games[appid] = entry
        entry["write"] = self._write(appid, entry, running)
        self._save()
        return entry

    def forget(self, appid: str) -> bool:
        appid = str(appid)
        entry = self.games.pop(appid, None)
        if entry:
            for _kind, path in self.files(appid, entry):
                gamesettings.restore(path)
        self._save()
        return entry is not None

    def set_tier(self, appid: str, tier: str, running: bool = False) -> dict | None:
        e = self.games.get(str(appid))
        if not e or tier not in TIERS:
            return None
        e["tier"], e["too_slow"] = tier, None       # your choice resets what Pitwall learned
        e["write"] = self._write(str(appid), e, running)
        self._save()
        return e

    def started(self, appid: str):
        e = self.games.get(str(appid))
        if e:
            e["started"] = time.time()
            self._save()

    def finished(self, appid: str, target: float, windows: list | None = None) -> dict | None:
        """After a session: keep the frames from while you were driving, move
        the level, then write the game's settings (it has closed now)."""
        appid = str(appid)
        e = self.games.get(appid)
        if not e:
            return None
        since = e.get("started")
        e["started"] = None
        result = {"changed": False, "message": None}
        path = newest_log(log_dir(self.base, appid), since, e.get("seen")) if since else None
        rows, how = racing_rows(path, windows or []) if path else ([], "none")
        driven = seconds_of(rows)
        if path:
            e["seen"] = os.path.basename(path)
        if rows and driven >= MIN_RACING_S:
            res = perf.analyse([r[1] for r in rows], target)
            if res.get("ok"):
                loads = [r[2] for r in rows if r[2] is not None]
                gpu = statistics.median(loads) if loads else None
                old = e["tier"]
                new, msg = decide(e, res, target, gpu)
                if TIERS.index(new) > TIERS.index(old):
                    tsl = e.get("too_slow")
                    e["too_slow"] = old if tsl is None or TIERS.index(old) > TIERS.index(tsl) else tsl
                e["tier"] = new
                e["runs"] = ([{"t": int(time.time()), "tier": old, "avg": res["avg_fps"], "low1": res["low1_fps"],
                               "gpu": gpu, "verdict": res["verdict"], "driven_s": int(driven), "how": how}]
                             + e.get("runs", []))[:5]
                speak = new != old or len(e["runs"]) == 1 or (res["verdict"] == "too_slow" and new == TIERS[-1])
                result = {"changed": new != old, "tier": new, "message": f"{e['name']} {msg}" if speak else None}
                if new != old:
                    e["pending"] = True
        elif path and how != "none":
            result["message"] = None        # too little driving to judge; nothing changes
        if e.get("pending"):
            e["write"] = self._write(appid, e)
        self._save()
        for p in glob.glob(os.path.join(log_dir(self.base, appid), "*.csv")):
            try:
                if os.path.getmtime(p) < time.time() - 86400:
                    os.remove(p)             # keep a day of logs
            except OSError:
                pass
        return result

    def status(self) -> list[dict]:
        out = []
        for appid, e in self.games.items():
            files = self.files(appid, e)
            w = e.get("write") or {}
            out.append({"appid": appid, "name": e["name"], "tier": e["tier"], "label": TIER_LABELS[e["tier"]],
                        "auto_settings": bool(files),
                        "files": [{"kind": k, "name": os.path.basename(p)} for k, p in files],
                        "pending": bool(e.get("pending")),
                        "advice": advice(e.get("game"), e["tier"], files), "last": (e.get("runs") or [None])[0],
                        "write_error": w.get("message") if w and not w.get("ok") else None})
        return sorted(out, key=lambda x: x["name"].lower())
