"""In-game button layout: one logical layout for your wheel, written into the
games Pitwall can configure, and shown to you everywhere else.

The layout maps actions (shift up, look back, horn...) to wheel controls
("346e:0005/b289"). Pitwall fills it in automatically from the wheel's
buttons; you can change any action by pressing the button you want.

BeamNG.drive is configured directly: Pitwall writes the wheel's input map
diff (settings/inputmaps/<pid><vid>.diff in the user folder), the same file
BeamNG writes when you rebind in its Controls menu. Bindings you made yourself
are kept; Pitwall only adds bindings for buttons that have none, and notes
which ones it added (in <file>.pitwall) so removing them leaves yours alone.
"""

from __future__ import annotations

import glob
import json
import os
import shutil

# Every in-game action Pitwall knows: (id, label, BeamNG action id or None).
ACTIONS = [
    ("shift_up", "Shift up", "shiftUp"),
    ("shift_down", "Shift down", "shiftDown"),
    ("handbrake", "Handbrake", "parkingbrake"),
    ("look_back", "Look back", "look_back"),
    ("camera", "Change camera", "switch_camera_next"),
    ("pit_limiter", "Pit limiter", None),
    ("ignition", "Ignition / engine", "activateStarterMotor"),
    ("starter", "Starter", None),
    ("lights", "Headlights", "toggle_headlights"),
    ("flash", "Flash headlights", None),
    ("wipers", "Wipers", None),
    ("horn", "Horn", "horn"),
    ("drs", "DRS", None),
    ("kers", "KERS / ERS deploy", None),
    ("tc_up", "Traction control +", None),
    ("tc_down", "Traction control -", None),
    ("abs_up", "ABS +", None),
    ("abs_down", "ABS -", None),
    ("bias_fwd", "Brake bias forward", None),
    ("bias_back", "Brake bias back", None),
    ("request_pit", "Request pit stop", None),
    ("radio", "Team radio", None),
    ("esc", "ESC / TC mode", "toggleESCMode"),
    ("left_signal", "Left indicator", "toggle_left_signal"),
    ("right_signal", "Right indicator", "toggle_right_signal"),
    ("hazards", "Hazard lights", "toggle_hazard_signal"),
    ("high_beam", "High beam", None),
    ("cruise", "Cruise control", None),
    ("trailer", "Attach trailer", None),
    ("rewind", "Rewind", None),
    ("reset", "Recover car", "recover_vehicle"),
    ("gearbox", "Gearbox mode", "toggleShifterMode"),
    ("radial", "Quick menu", "toggleRadialMenuMulti"),
    ("pause", "Pause / menu", "toggleMenues"),
]
LABELS = {a: l for a, l, _ in ACTIONS}
BEAMNG = {a: b for a, _, b in ACTIONS if b}
BEAMNG_APPID = "284160"

# The actions each game actually has, most useful first: the first ones get
# the easiest-to-reach buttons. Paddles are always shift up/down. Games not
# listed get the general list. Only BeamNG.drive is set up by Pitwall itself;
# for the others this is the layout to set in the game's controls menu.
_SIM = ["pit_limiter", "look_back", "ignition", "starter", "lights", "flash", "wipers", "tc_up", "tc_down",
        "abs_up", "abs_down", "bias_fwd", "bias_back", "request_pit", "left_signal", "right_signal", "camera", "pause"]
GAME_ACTIONS = {
    "beamng": ["handbrake", "look_back", "camera", "reset", "ignition", "lights", "horn", "esc",
               "left_signal", "right_signal", "hazards", "gearbox", "radial", "pause"],
    "ac": ["look_back", "camera", "drs", "kers", "lights", "horn", "tc_up", "tc_down", "abs_up", "abs_down",
           "bias_fwd", "bias_back", "handbrake", "pause"],
    "acc": ["pit_limiter", "look_back", "ignition", "starter", "lights", "flash", "wipers", "tc_up", "tc_down",
            "abs_up", "abs_down", "bias_fwd", "bias_back", "left_signal", "right_signal", "camera", "pause"],
    "ac_evo": ["pit_limiter", "look_back", "ignition", "starter", "lights", "flash", "wipers", "tc_up", "tc_down",
               "abs_up", "abs_down", "bias_fwd", "bias_back", "camera", "pause"],
    "lmu": _SIM, "rf2": _SIM, "ams2": _SIM, "pc2": _SIM, "raceroom": _SIM, "iracing": _SIM,
    "f1": ["drs", "pit_limiter", "kers", "radio", "look_back", "bias_fwd", "bias_back", "camera", "pause"],
    "forza": ["handbrake", "look_back", "camera", "rewind", "horn", "pause"],
    "rally": ["handbrake", "look_back", "camera", "lights", "wipers", "pause"],
    "trucks": ["handbrake", "ignition", "lights", "high_beam", "horn", "left_signal", "right_signal", "hazards",
               "wipers", "cruise", "trailer", "look_back", "camera", "pause"],
    "lfs": ["handbrake", "pit_limiter", "ignition", "lights", "horn", "left_signal", "right_signal", "hazards",
            "look_back", "camera", "pause"],
}
_FAMILY = {"f1_2021": "f1", "f1_22": "f1", "f1_23": "f1", "f1_24": "f1", "f1_25": "f1",
           "fh4": "forza", "fh5": "forza", "fh6": "forza", "fm": "forza",
           "dr2": "rally", "dirt_rally": "rally", "dirt_4": "rally", "eawrc": "rally", "ac_rally": "rally",
           "ets2": "trucks", "ats": "trucks"}
GENERAL = ["handbrake", "look_back", "camera", "pit_limiter", "lights", "horn", "ignition", "pause"]

# What the D-pad is for in each game (shown, not bound: the D-pad usually works
# as the game's menu or display navigation already).
DPAD_USE = {
    "acc": "Change the on-screen display pages (MFD)",
    "ac_evo": "Change the on-screen display pages",
    "lmu": "Change the on-screen display pages (MFD)", "rf2": "Change the on-screen display pages (MFD)",
    "ams2": "Change the on-screen display (ICM)", "pc2": "Change the on-screen display (ICM)",
    "iracing": "Change the black box pages",
    "f1": "Change the on-screen display (MFD)",
}


def game_family(game_id: str | None) -> str | None:
    if not game_id:
        return None
    return game_id if game_id in GAME_ACTIONS else _FAMILY.get(game_id)


def actions_for(game_id: str | None) -> list[str]:
    fam = game_family(game_id)
    return ["shift_up", "shift_down"] + (GAME_ACTIONS[fam] if fam else GENERAL)


def dpad_use(game_id: str | None) -> str | None:
    return DPAD_USE.get(game_family(game_id) or "")


# Wheels whose button numbering is known, by USB ID. Positions are the order
# games and Steam see the buttons in (from 0). Only what's confirmed is listed;
# everything else shows as "Button N" and you set it by pressing it.
_G29 = {"names": {0: "Cross", 1: "Square", 2: "Circle", 3: "Triangle", 4: "Right paddle", 5: "Left paddle",
                  6: "R2", 7: "L2", 8: "Share", 9: "Options", 10: "R3"},
        "paddles": {"shift_up": 4, "shift_down": 5}}
_G920 = {"names": {4: "Right paddle", 5: "Left paddle"}, "paddles": {"shift_up": 4, "shift_down": 5}}
KNOWN_WHEELS = {
    "046d:c24f": _G29,       # G29
    "046d:c267": _G29,       # G923 for PlayStation/PC
    "046d:c262": _G920,      # G920
    "046d:c26d": _G920,      # G923 for Xbox/PC
}


def known(dev_id: str) -> dict | None:
    return KNOWN_WHEELS.get(dev_id.lower())


def button_name(dev: dict, index: int) -> str | None:
    k = known(dev["id"])
    return (k or {}).get("names", {}).get(index)


def _control_index(control: str, devices: dict) -> tuple[dict, int] | None:
    dev_id, _, part = control.partition("/")
    dev = devices.get(dev_id)
    if not dev or not part.startswith("b") or not part[1:].isdigit():
        return None
    code = int(part[1:])
    if code not in dev["buttons"]:
        return None
    return dev, dev["buttons"].index(code)


def factory_paddles(dev: dict, factory: list | None) -> dict:
    """Paddle positions from BeamNG's own profile for this wheel, if it has one
    (BeamNG ships profiles for many wheels, the MOZA R3 included)."""
    out = {}
    for b in factory or []:
        c, a = b.get("control", ""), b.get("action")
        if c.startswith("button") and c[6:].isdigit() and a in ("shiftUp", "shiftDown"):
            idx = int(c[6:])
            if idx < len(dev["buttons"]):
                out.setdefault("shift_up" if a == "shiftUp" else "shift_down", idx)
    return out


def paddles_for(dev: dict, factory: list | None = None) -> dict:
    return dict((known(dev["id"]) or {}).get("paddles") or {}) or factory_paddles(dev, factory)


BEAMNG_REVERSE = {b: a for a, b in BEAMNG.items()}


def auto_layout(devices: dict, keep: dict | None = None, game_id: str | None = None,
                reserved: set | None = None, factory: dict | None = None) -> dict:
    """Assign this game's actions to wheel buttons.

    keep: actions you've set yourself (they win, in every game).
    factory: per device, the bindings of BeamNG's own profile for that wheel.
    Paddles come from Pitwall's table of known wheels or from that profile; on
    other wheels Pitwall asks you to press them once, because brands number
    them differently. In BeamNG, what its own profile already binds is kept as
    it is. The remaining actions go to free buttons in the game's order of
    usefulness."""
    factory = factory or {}
    wanted = actions_for(game_id)
    layout = {a: c for a, c in (keep or {}).items() if a in LABELS and c}
    used = set(reserved or ())
    for dev in devices.values():
        for action, idx in paddles_for(dev, factory.get(dev["id"])).items():
            c = f"{dev['id']}/b{dev['buttons'][idx]}"
            used.add(c)                                  # paddles never get another job
            layout.setdefault(action, c)
        if game_family(game_id) == "beamng":
            for b in factory.get(dev["id"]) or []:
                ctl = b.get("control", "")
                if not (ctl.startswith("button") and ctl[6:].isdigit()) or int(ctl[6:]) >= len(dev["buttons"]):
                    continue
                c = f"{dev['id']}/b{dev['buttons'][int(ctl[6:])]}"
                used.add(c)                              # BeamNG already uses this button
                ours = BEAMNG_REVERSE.get(b.get("action"))
                if ours and ours not in layout:
                    layout[ours] = c
    layout = {a: c for a, c in layout.items() if a in wanted}
    used |= set(layout.values())
    free = [f"{d['id']}/b{code}" for d in devices.values() for code in d["buttons"]]
    free = [c for c in free if c not in used]
    for action in wanted:
        if action in layout or action in ("shift_up", "shift_down"):
            continue
        if not free:
            break
        layout[action] = free.pop(0)
    return layout


def is_factory(action: str, control: str | None, devices: dict, factory: dict | None) -> bool:
    """True when BeamNG's own profile binds this button to this action."""
    hit = _control_index(control or "", devices)
    b = BEAMNG.get(action)
    if not hit or not b:
        return False
    dev, idx = hit
    return any(f.get("control") == f"button{idx}" and f.get("action") == b for f in (factory or {}).get(dev["id"]) or [])


def describe(layout: dict, devices: dict, label_fn, game_id: str | None = None) -> list[dict]:
    """Rows for the UI: this game's actions with the button each is on."""
    return [{"action": a, "label": LABELS[a], "control": layout.get(a),
             "button": label_fn(layout[a], devices) if layout.get(a) else None}
            for a in actions_for(game_id)]


def action_for(layout: dict, control: str) -> str | None:
    for a, c in layout.items():
        if c == control:
            return LABELS.get(a)
    return None


# ----------------------------------------------------------------- BeamNG
def beamng_user_folders(home: str, steam_roots: list[str] | None = None) -> list[str]:
    """Existing BeamNG user folders, however you run it on Linux: the native
    Linux build (also inside Flatpak Steam), or the Windows build under Proton,
    in its current, latest or versioned folder."""
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    datas = [xdg, os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share")]
    cands = []
    for d in datas:
        cands += [os.path.join(d, "BeamNG", "BeamNG.drive", "current"), os.path.join(d, "BeamNG.drive", "latest")]
        cands += sorted(glob.glob(os.path.join(d, "BeamNG.drive", "[0-9]*")),
                        key=lambda p: [int(x) if x.isdigit() else 0 for x in os.path.basename(p).split(".")])[-1:]
    if steam_roots is None:
        try:
            from .compat import steam_roots as _roots
            roots = _roots(home)
        except Exception:
            roots = []
        roots = roots or [os.path.join(home, ".local", "share", "Steam"), os.path.join(home, ".steam", "steam")]
    else:
        roots = steam_roots
    def newest(pattern):
        def ver(p):
            return [int(x) if x.isdigit() else 0 for x in os.path.basename(p).split(".")]
        found = sorted(glob.glob(pattern), key=ver)
        return found[-1:]

    for r in roots:
        local = os.path.join(r, "steamapps", "compatdata", BEAMNG_APPID, "pfx", "drive_c", "users", "steamuser",
                             "AppData", "Local")
        cands.append(os.path.join(local, "BeamNG", "BeamNG.drive", "current"))
        for name in ("BeamNG.drive", "BeamNG.Drive"):      # the Windows build has used both spellings
            cands.append(os.path.join(local, name, "latest"))
            cands.append(os.path.join(local, name, "current"))
            cands += newest(os.path.join(local, name, "[0-9]*"))
    out = []
    for c in cands:
        real = os.path.realpath(c)
        if os.path.isdir(c) and real not in {os.path.realpath(o) for o in out}:
            out.append(c)
    return out


def beamng_install_dirs(home: str, steam_roots: list[str] | None = None) -> list[str]:
    if steam_roots is None:
        try:
            from .compat import steam_roots as _roots
            steam_roots = _roots(home)
        except Exception:
            steam_roots = []
    return [d for r in steam_roots for d in [os.path.join(r, "steamapps", "common", "BeamNG.drive")] if os.path.isdir(d)]


_FACTORY_CACHE: dict = {}


def beamng_factory(home: str, dev_id: str, steam_roots: list[str] | None = None) -> list[dict]:
    """The bindings BeamNG ships for this wheel (settings/inputmaps/<pid><vid>.json
    in the game folder, loose or inside the game's zip archives), or []."""
    import zipfile
    stem = beamng_filename(dev_id)[:-len(".diff")]
    for inst in beamng_install_dirs(home, steam_roots):
        loose = sorted(glob.glob(os.path.join(inst, "settings", "inputmaps", f"{stem}*.json")))
        for p in loose:
            data = _read_json(p, None)
            if isinstance(data, dict) and isinstance(data.get("bindings"), list):
                return [b for b in data["bindings"] if isinstance(b, dict)]
        for z in sorted(glob.glob(os.path.join(inst, "*.zip")) + glob.glob(os.path.join(inst, "content", "*.zip"))):
            try:
                key = (z, os.path.getmtime(z), stem)
                if key in _FACTORY_CACHE:
                    if _FACTORY_CACHE[key]:
                        return _FACTORY_CACHE[key]
                    continue
                found: list = []
                with zipfile.ZipFile(z) as zf:
                    for name in zf.namelist():
                        base = name.rsplit("/", 1)[-1]
                        if name.startswith("settings/inputmaps/") and base.startswith(stem) and base.endswith(".json"):
                            data = json.loads(zf.read(name).decode("utf-8", "replace"))
                            if isinstance(data, dict) and isinstance(data.get("bindings"), list):
                                found = [b for b in data["bindings"] if isinstance(b, dict)]
                                break
                _FACTORY_CACHE[key] = found
                if found:
                    return found
            except (OSError, ValueError, zipfile.BadZipFile, KeyError):
                continue
    return []


def beamng_filename(dev_id: str) -> str:
    """'346e:0005' -> '0005346e.diff' (product ID then vendor ID, as BeamNG names them)."""
    vid, _, pid = dev_id.partition(":")
    return f"{pid.lower():0>4}{vid.lower():0>4}.diff"


def beamng_diffs(layout: dict, devices: dict, factory: dict | None = None) -> dict[str, list[dict]]:
    """Per device file name: the bindings Pitwall wants to add. Anything BeamNG's
    own profile already binds is left out: it's there by default."""
    factory = factory or {}
    out: dict[str, list[dict]] = {}
    for action, control in layout.items():
        b = BEAMNG.get(action)
        hit = _control_index(control, devices) if b else None
        if not hit:
            continue
        dev, idx = hit
        fac = factory.get(dev["id"]) or []
        if any(f.get("control") == f"button{idx}" or f.get("action") == b for f in fac):
            continue
        out.setdefault(beamng_filename(dev["id"]), []).append(
            {"control": f"button{idx}", "action": b})
    return out


def _key(b: dict) -> tuple:
    return (b.get("control"), b.get("action"))


def _read_json(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _merge(existing: dict, previous: list[dict], ours: list[dict], name: str) -> tuple[dict, list[dict]]:
    """Returns the new file and the bindings Pitwall added (kept in a side file,
    so the diff itself stays exactly in BeamNG's format)."""
    data = dict(existing or {})
    data.setdefault("version", 1)
    data.setdefault("devicetype", "joystick")
    data.setdefault("name", name)
    data.setdefault("displayName", name)
    prev = {_key(b) for b in (previous if isinstance(previous, list) else []) if isinstance(b, dict)}
    old = data.get("bindings")
    yours = [b for b in (old if isinstance(old, list) else []) if isinstance(b, dict) and _key(b) not in prev]
    taken = {b.get("control") for b in yours} | {b.get("action") for b in yours}
    rem = data.get("removed")
    removed = {_key(r) for r in (rem if isinstance(rem, list) else []) if isinstance(r, dict)}
    added = []
    for b in ours:
        if b["control"] in taken or b["action"] in taken or _key(b) in removed:
            continue                        # your own binding or removal wins
        added.append(b)
    data["bindings"] = yours + added
    return data, added


def beamng_apply(home: str, layout: dict, devices: dict, steam_roots=None, factory: dict | None = None) -> dict:
    folders = beamng_user_folders(home, steam_roots)
    if not folders:
        return {"ok": False, "error": "BeamNG.drive's user folder wasn't found. Start BeamNG once, then try again.",
                "written": []}
    wanted = beamng_diffs(layout, devices, factory)
    if not wanted:
        return {"ok": True, "error": None, "written": [], "message": "BeamNG's own profile already covers these buttons."}
    written = []
    for folder in folders:
        d = os.path.join(folder, "settings", "inputmaps")
        os.makedirs(d, exist_ok=True)
        for fname, ours in wanted.items():
            path = os.path.join(d, fname)
            side = path + ".pitwall"
            existing = {}
            if os.path.exists(path):
                if not os.path.exists(path + ".pitwall-backup") and not os.path.exists(side):
                    shutil.copy2(path, path + ".pitwall-backup")
                existing = _read_json(path, {})
                if not isinstance(existing, dict):
                    existing = {}
            dev = devices.get(next((k for k in devices if beamng_filename(k) == fname), ""), {})
            data, added = _merge(existing, _read_json(side, []), ours, dev.get("name", "Wheel"))
            for target, content in ((path, data), (side, added)):
                tmp = target + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(content, f, indent=2)
                os.replace(tmp, target)
            written.append(path)
    return {"ok": True, "error": None, "written": written}


def beamng_status(home: str, steam_roots=None) -> dict:
    folders = beamng_user_folders(home, steam_roots)
    applied = [s[: -len(".pitwall")] for f in folders
               for s in glob.glob(os.path.join(f, "settings", "inputmaps", "*.diff.pitwall"))]
    return {"found": bool(folders), "folders": folders, "applied": bool(applied)}


def beamng_remove(home: str, steam_roots=None) -> list[str]:
    """Take Pitwall's bindings out again (your own stay)."""
    done = []
    for folder in beamng_user_folders(home, steam_roots):
        for side in glob.glob(os.path.join(folder, "settings", "inputmaps", "*.diff.pitwall")):
            path = side[: -len(".pitwall")]
            side_data = _read_json(side, [])
            ours = {_key(b) for b in (side_data if isinstance(side_data, list) else []) if isinstance(b, dict)}
            data = _read_json(path, None)
            backup = path + ".pitwall-backup"
            if isinstance(data, dict):
                old = data.get("bindings")
                data["bindings"] = [b for b in (old if isinstance(old, list) else [])
                                    if not (isinstance(b, dict) and _key(b) in ours)]
                if data["bindings"] or data.get("removed") or os.path.exists(backup):
                    with open(path, "w") as f:
                        json.dump(data, f, indent=2)
                else:
                    os.remove(path)
            if os.path.exists(backup):
                os.remove(backup)       # your later changes are in the file itself now
            os.remove(side)
            done.append(path)
    return done


# ----------------------------------------------------------------- diagram
def diagram_svg(layout: dict, devices: dict, game_id: str | None, factory: dict | None = None) -> str:
    """A small picture of the wheel for one game: the paddles, the D-pad and a
    numbered dot per bound button, with a key underneath. The dots are laid out
    evenly, not where each button physically sits (that differs per wheel); the
    numbers match what Pitwall shows when you press a button."""
    from html import escape
    up, down = layout.get("shift_up"), layout.get("shift_down")
    items = []
    for action in actions_for(game_id):
        c = layout.get(action)
        if action in ("shift_up", "shift_down") or not c:
            continue
        hit = _control_index(c, devices)
        if not hit:
            continue
        dev, idx = hit
        name = button_name(dev, idx)
        items.append((idx, dev["id"], LABELS[action], name))
    items.sort(key=lambda x: (x[1], x[0]))
    w, cx, cy, r = 320, 160, 100, 78
    rows = (len(items) + 1) // 2
    h = 200 + 18 * max(rows, 1) + 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" '
           f'aria-label="Wheel buttons for this game" font-family="system-ui,sans-serif" font-size="11" fill="currentColor">']
    # paddles behind the rim
    for side, x, label in ((-1, cx - r - 6, "Shift down" if down else "Left paddle: not set"),
                           (1, cx + r + 6, "Shift up" if up else "Right paddle: not set")):
        out.append(f'<rect x="{x - 9}" y="{cy - 46}" width="18" height="40" rx="6" fill="currentColor" opacity="0.35"/>')
        anchor = "end" if side < 0 else "start"
        tx = x - 14 if side < 0 else x + 14
        out.append(f'<text x="{tx}" y="{cy - 22}" text-anchor="{anchor}" font-weight="600">{escape(label)}</text>')
    # rim and hub
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="currentColor" stroke-width="12" opacity="0.55"/>')
    out.append(f'<rect x="{cx - 52}" y="{cy - 30}" width="104" height="62" rx="16" fill="currentColor" opacity="0.12"/>')
    # D-pad on the left of the hub
    dx, dy = cx - 32, cy + 1
    for ax, ay, aw, ah in ((dx - 4, dy - 13, 8, 26), (dx - 13, dy - 4, 26, 8)):
        out.append(f'<rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" rx="2" fill="currentColor" opacity="0.6"/>')
    # numbered dots on the right of the hub, evenly spaced
    shown = items[:8]
    for i, (idx, _dev, _label, _n) in enumerate(shown):
        col, row = i % 4, i // 4
        bx, by = cx - 4 + col * 15, cy - 12 + row * 22
        out.append(f'<circle cx="{bx}" cy="{by}" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/>')
        out.append(f'<text x="{bx}" y="{by + 3.5}" text-anchor="middle" font-size="8.5" font-weight="700">{idx + 1}</text>')
    dpad = dpad_use(game_id)
    y0 = cy + r + 22
    out.append(f'<text x="8" y="{y0}" font-weight="600">D-pad: {escape(dpad or "menus and the game\'s own use")}</text>')
    for i, (idx, _dev, label, name) in enumerate(items):
        col, row = i % 2, i // 2
        tx, ty = 8 + col * 156, y0 + 18 + row * 18
        key = f"{idx + 1}"
        out.append(f'<circle cx="{tx + 7}" cy="{ty - 4}" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/>')
        out.append(f'<text x="{tx + 7}" y="{ty - 0.5}" text-anchor="middle" font-size="8.5" font-weight="700">{key}</text>')
        text = label if not name else f"{label} ({name})"
        out.append(f'<text x="{tx + 19}" y="{ty}">{escape(text[:24])}</text>')
    if not items:
        out.append(f'<text x="8" y="{y0 + 18}" opacity="0.7">No buttons set yet for this game.</text>')
    out.append("</svg>")
    return "".join(out)
