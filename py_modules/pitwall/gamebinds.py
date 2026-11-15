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


def auto_layout(devices: dict, keep: dict | None = None, game_id: str | None = None,
                reserved: set | None = None) -> dict:
    """Assign this game's actions to wheel buttons.

    keep: actions you've set yourself (they win, in every game). Paddles are
    set automatically on wheels whose numbering is known; on others Pitwall
    asks you to press them once, because brands number them differently.
    The remaining actions go to free buttons in the game's order of usefulness."""
    wanted = actions_for(game_id)
    layout = {a: c for a, c in (keep or {}).items() if a in LABELS and c}
    for dev in devices.values():
        k = known(dev["id"])
        for action, idx in ((k or {}).get("paddles") or {}).items():
            if action not in layout and idx < len(dev["buttons"]):
                layout[action] = f"{dev['id']}/b{dev['buttons'][idx]}"
    layout = {a: c for a, c in layout.items() if a in wanted}
    used = set(layout.values()) | set(reserved or ())
    # Known paddle buttons are never handed out to other actions.
    for dev in devices.values():
        for idx in ((known(dev["id"]) or {}).get("paddles") or {}).values():
            if idx < len(dev["buttons"]):
                used.add(f"{dev['id']}/b{dev['buttons'][idx]}")
    free = [f"{d['id']}/b{code}" for d in devices.values() for code in d["buttons"]]
    free = [c for c in free if c not in used]
    for action in wanted:
        if action in layout or action in ("shift_up", "shift_down"):
            continue
        if not free:
            break
        layout[action] = free.pop(0)
    return layout


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
    """Existing BeamNG user folders: native Linux and Proton, current and versioned."""
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    cands = [os.path.join(xdg, "BeamNG", "BeamNG.drive", "current"), os.path.join(xdg, "BeamNG.drive", "latest")]
    cands += sorted(glob.glob(os.path.join(xdg, "BeamNG.drive", "[0-9]*")))[-1:]
    roots = steam_roots or [os.path.join(home, ".local", "share", "Steam"), os.path.join(home, ".steam", "steam")]
    for r in roots:
        local = os.path.join(r, "steamapps", "compatdata", BEAMNG_APPID, "pfx", "drive_c", "users", "steamuser",
                             "AppData", "Local")
        cands.append(os.path.join(local, "BeamNG", "BeamNG.drive", "current"))
        cands.append(os.path.join(local, "BeamNG.drive", "latest"))
        cands += sorted(glob.glob(os.path.join(local, "BeamNG.drive", "[0-9]*")))[-1:]
    out = []
    for c in cands:
        real = os.path.realpath(c)
        if os.path.isdir(c) and real not in {os.path.realpath(o) for o in out}:
            out.append(c)
    return out


def beamng_filename(dev_id: str) -> str:
    """'346e:0005' -> '0005346e.diff' (product ID then vendor ID, as BeamNG names them)."""
    vid, _, pid = dev_id.partition(":")
    return f"{pid.lower():0>4}{vid.lower():0>4}.diff"


def beamng_diffs(layout: dict, devices: dict) -> dict[str, list[dict]]:
    """Per device file name: the bindings Pitwall wants."""
    out: dict[str, list[dict]] = {}
    for action, control in layout.items():
        b = BEAMNG.get(action)
        hit = _control_index(control, devices) if b else None
        if not hit:
            continue
        dev, idx = hit
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


def beamng_apply(home: str, layout: dict, devices: dict, steam_roots=None) -> dict:
    folders = beamng_user_folders(home, steam_roots)
    if not folders:
        return {"ok": False, "error": "BeamNG.drive's user folder wasn't found. Start BeamNG once, then try again.",
                "written": []}
    wanted = beamng_diffs(layout, devices)
    if not wanted:
        return {"ok": False, "error": "No wheel buttons to bind yet.", "written": []}
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
