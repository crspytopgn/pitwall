"""Changing a game's own graphics settings files, by file format.

Rather than one writer per game, Pitwall recognises the settings files that
whole engines use, and looks for them where that game keeps its files (its
Proton prefix, or its Linux folder for native games):

- Unreal Engine games: GameUserSettings.ini, [ScalabilityGroups] sg.* levels
  (0 low to 3 epic) and sg.ResolutionQuality (render scale %)
- Codemasters EGO games (F1, DiRT, GRID): hardware_settings_config.xml,
  render resolution and ray tracing
- Madness engine games (Automobilista 2, Project CARS 2 and 3):
  graphicsconfigdx11.xml, detail levels, motion blur, supersampling, resolution
- SCS games (Euro Truck Simulator 2, American Truck Simulator): config.cfg,
  render scale, sun shadows, mirror distance, SSAO, depth of field
- Assetto Corsa: video.ini (in graphics.py)

Rules for every format:
- only settings already in the file are changed; nothing is added
- the file is backed up once (<file>.pitwall-backup) and Stop tuning restores it
- relative changes are made from the backup, i.e. from your own settings, so
  "Max" means what you chose in the game and each level below turns detail
  down from there
- render resolution is only ever lowered, never raised past yours
- files are written only while the game isn't running, because games save
  their settings on exit and would undo the change
"""

from __future__ import annotations

import glob
import math
import os
import re
import shutil

TIERS = ["max", "high", "balanced", "performance"]
STEPS = {"max": 0, "high": 1, "balanced": 2, "performance": 3}
RENDER_H = {"max": None, "high": None, "balanced": 1440, "performance": 1080}

KIND_LABELS = {
    "beamng": "BeamNG.drive's settings.json",
    "ac": "Assetto Corsa's video.ini",
    "unreal": "the game's Unreal Engine settings (GameUserSettings.ini)",
    "ego": "the game's hardware_settings_config.xml",
    "madness": "the game's graphicsconfigdx11.xml",
    "scs": "the game's config.cfg",
}
SCS_FOLDERS = ("Euro Truck Simulator 2", "American Truck Simulator")
MADNESS_FOLDERS = ("Automobilista 2", "Project CARS 2", "Project CARS 3")


def user_dir(prefix: str) -> str:
    return os.path.join(prefix, "drive_c", "users", "steamuser")


def find(prefix: str | None, home: str, game_id: str | None = None) -> list[tuple[str, str]]:
    """(kind, path) for every settings file Pitwall can change for this game."""
    out: list[tuple[str, str]] = []
    if prefix:
        u = user_dir(prefix)
        ac = os.path.join(u, "Documents", "Assetto Corsa", "cfg", "video.ini")
        if os.path.isfile(ac):
            out.append(("ac", ac))
        for p in sorted(glob.glob(os.path.join(u, "AppData", "Local", "*", "Saved", "Config", "*", "GameUserSettings.ini"))):
            if "Epic" not in p.split(os.sep)[-5]:           # not a launcher's own settings
                out.append(("unreal", p))
        for p in sorted(glob.glob(os.path.join(u, "Documents", "My Games", "*", "hardwaresettings", "hardware_settings_config.xml"))):
            out.append(("ego", p))
        for folder in MADNESS_FOLDERS:
            p = os.path.join(u, "Documents", folder, "graphicsconfigdx11.xml")
            if os.path.isfile(p):
                out.append(("madness", p))
        for folder in SCS_FOLDERS:
            p = os.path.join(u, "Documents", folder, "config.cfg")
            if os.path.isfile(p):
                out.append(("scs", p))
    # BeamNG.drive: settings/settings.json in its user folder(s), native or Proton.
    if game_id == "beamng":
        try:
            from .gamebinds import beamng_user_folders
            for folder in beamng_user_folders(home):
                p = os.path.join(folder, "settings", "settings.json")
                if os.path.isfile(p):
                    out.append(("beamng", p))
        except Exception:
            pass
    # Native Linux builds of the SCS games keep their settings in your home.
    native = {"ets2": SCS_FOLDERS[0], "ats": SCS_FOLDERS[1]}.get(game_id or "")
    if native:
        p = os.path.join(home, ".local", "share", native, "config.cfg")
        if os.path.isfile(p):
            out.append(("scs", p))
    return out


# ------------------------------------------------------------------ helpers
def _read(path: str) -> str:
    with open(path, errors="replace", newline="") as f:
        return f.read()


def baseline(kind: str, path: str, current: str) -> str:
    """Your own settings, which relative changes start from: the file as it was
    before Pitwall's first change. Games rewrite their settings files on exit,
    so a changed file alone means nothing; but if any setting Pitwall controls
    no longer has the value Pitwall gave it, you changed it in the game, and
    the file as you left it becomes your settings."""
    base_p, written_p = path + ".pitwall-base", path + ".pitwall-written"
    if not os.path.exists(base_p):
        return current
    try:
        import json
        with open(written_p) as f:
            last_tier = json.load(f).get("tier")
        base = _read(base_p)
    except (OSError, ValueError, AttributeError):
        return current
    if last_tier not in TIERS:
        return current
    _, still_needed = WRITERS[kind](current, base, last_tier)
    return base if not still_needed else current


def _num(s: str) -> float | None:
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _fmt(v: float, like: str) -> str:
    """Write a number the way the file wrote it (int, or same decimals)."""
    if "." not in like:
        return str(int(round(v)))
    decimals = len(like.split(".", 1)[1])
    return f"{v:.{decimals}f}"


def _lower_res(w: float, h: float, tier: str) -> tuple[int, int] | None:
    cap = RENDER_H[tier]
    if not cap or h <= cap:
        return None
    return int(round(w * cap / h)), cap


def _sub(pattern: str, text: str, fn, flags=0) -> tuple[str, list[str]]:
    """Replace group 2 of each match with fn(old) (None: leave it)."""
    done: list[str] = []

    def rep(m):
        new = fn(m.group(2))
        if new is None or new == m.group(2):
            return m.group(0)
        done.append(new)
        return m.group(1) + new + m.group(3)
    return re.sub(pattern, rep, text, flags=flags), done


def _value(pattern: str, text: str, flags=0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(2) if m else None


# ------------------------------------------------------------------ Unreal
UE_LEVEL = {"max": 3, "high": 2, "balanced": 1, "performance": 0}
UE_TEXTURE = {"max": 3, "high": 2, "balanced": 2, "performance": 1}    # textures cost memory, not much speed
UE_RES = {"max": 100, "high": 100, "balanced": 75, "performance": 60}
UE_GROUPS = ["ViewDistanceQuality", "AntiAliasingQuality", "ShadowQuality", "GlobalIlluminationQuality",
             "ReflectionQuality", "PostProcessQuality", "EffectsQuality", "FoliageQuality", "ShadingQuality"]


def unreal(current: str, base: str, tier: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    text = current
    for g in UE_GROUPS + ["TextureQuality"]:
        lvl = (UE_TEXTURE if g == "TextureQuality" else UE_LEVEL)[tier]
        text, d = _sub(rf"(?m)^(\s*sg\.{g}\s*=\s*)(-?\d+)(\s*)$", text, lambda old, lvl=lvl: str(lvl))
        changes += [f"{g}={x}" for x in d]
    b = _num(_value(r"(?m)^(\s*sg\.ResolutionQuality\s*=\s*)([\d.]+)(\s*)$", base) or "")
    if b is not None:
        want = min(b, UE_RES[tier])
        text, d = _sub(r"(?m)^(\s*sg\.ResolutionQuality\s*=\s*)([\d.]+)(\s*)$", text, lambda old: _fmt(want, old))
        changes += [f"ResolutionQuality={x}" for x in d]
    return text, changes


# ------------------------------------------------------------------ Codemasters EGO
def ego(current: str, base: str, tier: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    text = current
    bw = _num(_value(r'(<resolution\b[^>]*\bwidth=")(\d+)(")', base) or "")
    bh = _num(_value(r'(<resolution\b[^>]*\bheight=")(\d+)(")', base) or "")
    if bw and bh:
        res = _lower_res(bw, bh, tier) or (int(bw), int(bh))
        text, d = _sub(r'(<resolution\b[^>]*\bwidth=")(\d+)(")', text, lambda o: str(res[0]))
        text, d2 = _sub(r'(<resolution\b[^>]*\bheight=")(\d+)(")', text, lambda o: str(res[1]))
        changes += [f"resolution {res[0]}x{res[1]}"] if d or d2 else []
    for el in ("rt_shadows", "rt_reflections", "rt_transparent_reflections", "rt_ao"):
        was = _value(rf'(<{el}\b[^>]*\benabled=")(true|false)(")', base)
        if was is None:
            continue
        want = was if tier == "max" else "false"           # ray tracing is very heavy on this GPU class
        text, d = _sub(rf'(<{el}\b[^>]*\benabled=")(true|false)(")', text, lambda o, w=want: w)
        changes += [f"{el}={x}" for x in d]
    return text, changes


# ------------------------------------------------------------------ Madness (AMS2, PC2, PC3)
MADNESS_DETAIL = ["ShadowDetailLevel", "EnvmapDetailLevel", "EnvmapReflectionDetailLevel", "TrackDetailLevel",
                  "CarDetailLevel", "EffectsDetailLevel"]


def _prop(name: str) -> str:
    return rf'(<prop\s+name="{name}"\s+{name.lower()}=")(-?\d+)(")'


def madness(current: str, base: str, tier: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    text = current
    steps = STEPS[tier]
    for name in MADNESS_DETAIL:
        b = _num(_value(_prop(name), base) or "")
        if b is None:
            continue
        want = str(int(max(0, b - steps)))
        text, d = _sub(_prop(name), text, lambda o, w=want: w)
        changes += [f"{name}={x}" for x in d]
    for name in ("MotionblurLevel", "SuperSampling", "LowSuperSampling"):
        b = _value(_prop(name), base)
        if b is None:
            continue
        want = b if tier == "max" else "0"
        text, d = _sub(_prop(name), text, lambda o, w=want: w)
        changes += [f"{name}={x}" for x in d]
    mode = r'(<prop\s+name="Mode"[^>]*\b{attr}=")(\d+)(")'
    bw = _num(_value(mode.format(attr="width"), base) or "")
    bh = _num(_value(mode.format(attr="height"), base) or "")
    if bw and bh:
        res = _lower_res(bw, bh, tier) or (int(bw), int(bh))
        text, d = _sub(mode.format(attr="width"), text, lambda o: str(res[0]))
        text, d2 = _sub(mode.format(attr="height"), text, lambda o: str(res[1]))
        changes += [f"resolution {res[0]}x{res[1]}"] if d or d2 else []
    return text, changes


# ------------------------------------------------------------------ SCS (ETS2, ATS)
def _uset(key: str) -> str:
    return rf'(?m)^(\s*uset\s+{key}\s+")([^"]*)(")'


def scs(current: str, base: str, tier: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    text = current
    steps = STEPS[tier]
    factor = {"max": 1.0, "high": 1.0, "balanced": 0.8, "performance": 0.6}[tier]
    for key in ("r_scale_x", "r_scale_y"):
        raw = _value(_uset(key), base)
        b = _num(raw or "")
        if b is None:
            continue
        want = round(b * math.sqrt(factor), 2)          # the render scale is x times y
        new = raw if factor == 1.0 else f"{want:.2f}".rstrip("0").rstrip(".")
        text, d = _sub(_uset(key), text, lambda o, w=new: w)
        changes += [f"{key}={x}" for x in d]
    b = _num(_value(_uset("r_sun_shadow_quality"), base) or "")
    if b is not None:
        text, d = _sub(_uset("r_sun_shadow_quality"), text, lambda o, w=str(int(max(0, b - steps))): w)
        changes += [f"r_sun_shadow_quality={x}" for x in d]
    b = _num(_value(_uset("r_sun_shadow_texture_size"), base) or "")
    if b is not None:
        want = str(int(max(1024, b / (2 ** steps)))) if b >= 1024 else str(int(b))
        text, d = _sub(_uset("r_sun_shadow_texture_size"), text, lambda o, w=want: w)
        changes += [f"r_sun_shadow_texture_size={x}" for x in d]
    b = _num(_value(_uset("r_mirror_view_distance"), base) or "")
    if b is not None:
        want = b * {"max": 1.0, "high": 0.8, "balanced": 0.6, "performance": 0.4}[tier]
        text, d = _sub(_uset("r_mirror_view_distance"), text, lambda o, w=want: _fmt(w, o))
        changes += [f"r_mirror_view_distance={x}" for x in d]
    for key, off_from in (("r_ssao", "balanced"), ("r_dof", "high")):
        b = _value(_uset(key), base)
        if b is None:
            continue
        want = "0" if STEPS[tier] >= STEPS[off_from] else b
        text, d = _sub(_uset(key), text, lambda o, w=want: w)
        changes += [f"{key}={x}" for x in d]
    return text, changes


# ------------------------------------------------------------------ BeamNG.drive
BNG_LADDER = ["Lowest", "Low", "Normal", "High", "Ultra"]
BNG_LIGHTING = ["Lowest", "Low", "High", "Ultra"]            # BeamNG 0.40 has no Normal lighting
BNG_QUALITY = {"GraphicMeshQuality": 1, "GraphicShadowsQuality": 1, "GraphicTerrainQuality": 1,
               "GraphicTextureQuality": 0.5, "GraphicLightingQuality": 1}     # steps per level


def beamng(current: str, base: str, tier: str) -> tuple[str, list[str]]:
    import json
    try:
        cur, b = json.loads(current), json.loads(base)
    except ValueError:
        return current, []
    if not isinstance(cur, dict) or not isinstance(b, dict):
        return current, []
    steps = STEPS[tier]
    new = dict(cur)

    def down(key, ladder, n):
        v = b.get(key)
        if key in cur and isinstance(v, str) and v in ladder:
            new[key] = ladder[max(0, ladder.index(v) - n)]

    for key, rate in BNG_QUALITY.items():
        down(key, BNG_LIGHTING if key == "GraphicLightingQuality" else BNG_LADDER, int(steps * rate))
    for key in ("GraphicDynReflectionEnabled", "PostFXMotionBlurEnabled", "PostFXDOFGeneralEnabled"):
        if key in cur and isinstance(b.get(key), bool):
            new[key] = b[key] if tier == "max" else False      # dynamic reflections are the heaviest setting
    g = b.get("GraphicGrassDensity")
    if "GraphicGrassDensity" in cur and isinstance(g, (int, float)) and not isinstance(g, bool):
        new["GraphicGrassDensity"] = round(g * {"max": 1, "high": 0.75, "balanced": 0.5, "performance": 0.25}[tier], 2)
    a = b.get("GraphicAnisotropic")
    if "GraphicAnisotropic" in cur and isinstance(a, int) and not isinstance(a, bool):
        new["GraphicAnisotropic"] = max(0, min(a, {"max": a, "high": 16, "balanced": 8, "performance": 4}[tier]))
    res = b.get("GraphicDisplayResolutions")
    if "GraphicDisplayResolutions" in cur and isinstance(res, str):
        parts = res.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            lw = _lower_res(int(parts[0]), int(parts[1]), tier)
            new["GraphicDisplayResolutions"] = f"{lw[0]} {lw[1]}" if lw else res
    controlled = list(BNG_QUALITY) + ["GraphicDynReflectionEnabled", "PostFXMotionBlurEnabled",
                                      "PostFXDOFGeneralEnabled", "GraphicGrassDensity", "GraphicAnisotropic",
                                      "GraphicDisplayResolutions"]
    if "GraphicOverallQuality" in cur:
        lowered = any(new.get(k) != b.get(k) for k in controlled if k in cur and k in b)
        # A lowered level needs BeamNG's Custom preset, or it would apply its own
        # preset over these; Max is your own settings, preset included.
        new["GraphicOverallQuality"] = "Custom" if lowered else b.get("GraphicOverallQuality", cur["GraphicOverallQuality"])
    changes = [f"{k}={new[k]}" for k in new if new[k] != cur.get(k)]
    if not changes:
        return current, []
    return json.dumps(new, indent=2), changes


WRITERS = {"unreal": unreal, "ego": ego, "madness": madness, "scs": scs, "beamng": beamng}


def apply(kind: str, path: str, tier: str) -> dict:
    """Change one settings file to a level. Returns {ok, changed, path}."""
    fn = WRITERS[kind]
    try:
        current = _read(path)
        base = baseline(kind, path, current)
    except OSError as e:
        return {"ok": False, "message": f"Couldn't read {os.path.basename(path)}: {e.strerror}", "path": path}
    new, changes = fn(current, base, tier)
    backup = path + ".pitwall-backup"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)              # the original, for Stop tuning
    _write(path + ".pitwall-base", base)
    if new != current:
        _write(path, new)
    import json
    _write(path + ".pitwall-written", json.dumps({"tier": tier}))
    return {"ok": True, "changed": changes, "path": path}


def _write(path: str, text: str):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def sidecars(path: str) -> list[str]:
    return [path + s for s in (".pitwall-backup", ".pitwall-base", ".pitwall-written")]


def restore(path: str) -> bool:
    """Put your original settings back and forget Pitwall's notes."""
    b = path + ".pitwall-backup"
    ok = False
    if os.path.exists(b):
        os.replace(b, path)
        ok = True
    for extra in sidecars(path)[1:]:
        if os.path.exists(extra):
            os.remove(extra)
    return ok
