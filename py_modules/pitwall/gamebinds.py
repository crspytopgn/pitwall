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

# (id, label, BeamNG action id or None)
ACTIONS = [
    ("shift_up", "Shift up", "shiftUp"),
    ("shift_down", "Shift down", "shiftDown"),
    ("handbrake", "Handbrake", "parkingbrake"),
    ("look_back", "Look back", "look_back"),
    ("camera", "Change camera", "switch_camera_next"),
    ("reset", "Recover car", "recover_vehicle"),
    ("ignition", "Ignition / engine", "activateStarterMotor"),
    ("lights", "Headlights", "toggle_headlights"),
    ("horn", "Horn", "horn"),
    ("esc", "ESC / TC mode", "toggleESCMode"),
    ("left_signal", "Left indicator", "toggle_left_signal"),
    ("right_signal", "Right indicator", "toggle_right_signal"),
    ("hazards", "Hazard lights", "toggle_hazard_signal"),
    ("gearbox", "Gearbox mode", "toggleShifterMode"),
    ("radial", "Quick menu", "toggleRadialMenuMulti"),
    ("pause", "Pause / menu", "toggleMenues"),
]
LABELS = {a: l for a, l, _ in ACTIONS}
BEAMNG = {a: b for a, _, b in ACTIONS if b}
# Filled in this order onto buttons left after the paddles.
AUTO_ORDER = ["handbrake", "look_back", "camera", "reset", "ignition", "lights", "horn", "esc",
              "left_signal", "right_signal", "hazards", "gearbox", "radial", "pause"]
BEAMNG_APPID = "284160"


def _control_index(control: str, devices: dict) -> tuple[dict, int] | None:
    dev_id, _, part = control.partition("/")
    dev = devices.get(dev_id)
    if not dev or not part.startswith("b") or not part[1:].isdigit():
        return None
    code = int(part[1:])
    if code not in dev["buttons"]:
        return None
    return dev, dev["buttons"].index(code)


def auto_layout(devices: dict, keep: dict | None = None, reserved: set | None = None) -> dict:
    """Assign every action that isn't already set to a free wheel button.

    keep: actions already set (the user's choices win). reserved: controls
    not to use (e.g. ones the user marked as left alone). Paddles are not
    guessed here: button numbering differs between brands, so the UI asks
    you to press them once."""
    layout = {a: c for a, c in (keep or {}).items() if a in LABELS and c}
    used = set(layout.values()) | set(reserved or ())
    free = [f"{d['id']}/b{code}" for d in devices.values() for code in d["buttons"]]
    free = [c for c in free if c not in used]
    for action in AUTO_ORDER:
        if action in layout:
            continue
        if not free:
            break
        layout[action] = free.pop(0)
    return layout


def describe(layout: dict, devices: dict, label_fn) -> list[dict]:
    """Rows for the UI: every action with the button it's on, in order."""
    return [{"action": a, "label": l, "control": layout.get(a),
             "button": label_fn(layout[a], devices) if layout.get(a) else None}
            for a, l, _ in ACTIONS]


def action_for(layout: dict, control: str) -> str | None:
    for a, c in layout.items():
        if c == control:
            return LABELS.get(a)
    return None


# ----------------------------------------------------------------- BeamNG
def beamng_user_folders(home: str, steam_roots: list[str] | None = None) -> list[str]:
    """Existing BeamNG user folders: native Linux and Proton, current and versioned."""
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    cands = [os.path.join(xdg, "BeamNG", "BeamNG.drive", "current")]
    cands += sorted(glob.glob(os.path.join(xdg, "BeamNG.drive", "[0-9]*")))[-1:]
    roots = steam_roots or [os.path.join(home, ".local", "share", "Steam"), os.path.join(home, ".steam", "steam")]
    for r in roots:
        local = os.path.join(r, "steamapps", "compatdata", BEAMNG_APPID, "pfx", "drive_c", "users", "steamuser",
                             "AppData", "Local")
        cands.append(os.path.join(local, "BeamNG", "BeamNG.drive", "current"))
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
    prev = {_key(b) for b in previous}
    yours = [b for b in data.get("bindings", []) if isinstance(b, dict) and _key(b) not in prev]
    taken = {b.get("control") for b in yours} | {b.get("action") for b in yours}
    removed = {_key(r) for r in data.get("removed", []) if isinstance(r, dict)}
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
            ours = {_key(b) for b in _read_json(side, [])}
            data = _read_json(path, None)
            backup = path + ".pitwall-backup"
            if isinstance(data, dict):
                data["bindings"] = [b for b in data.get("bindings", []) if not (isinstance(b, dict) and _key(b) in ours)]
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
