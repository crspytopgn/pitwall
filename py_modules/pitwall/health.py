"""Pre-race health checks: is everything in place before you drive?"""

from __future__ import annotations

import glob
import json
import os
import platform
import re
import shutil

_WHEELS = os.path.join(os.path.dirname(__file__), "data", "wheels.json")
try:
    with open(_WHEELS) as _f:
        WHEEL_DB = json.load(_f)
except (OSError, ValueError):
    WHEEL_DB = {"wheels": []}

# Vendor IDs that only make sim racing hardware. Anything else (Logitech, Thrustmaster,
# STMicro's shared 0483, PXN's 11ff) also makes mice, keyboards or gamepads, so those
# count as wheels only when the exact product ID is in the table.
WHEEL_ONLY_VENDORS = {"346e": "MOZA", "0eb7": "Fanatec", "2433": "Asetek", "3416": "Cammus", "3670": "Simagic"}
_BY_ID: dict[tuple, list] = {}
for _w in WHEEL_DB["wheels"]:
    if _w.get("vid") and _w.get("pid"):
        _BY_ID.setdefault((_w["vid"], _w["pid"]), []).append(_w)


def identify(vid: str, pid: str) -> dict | None:
    """Look a wheel up in the community-tested support table. Some bases share a
    USB ID (MOZA R16 and R21, several Simagic and Fanatec bases), so matches are
    merged: 'R16 (v1/v2) / R21 (v1/v2)'."""
    rows = _BY_ID.get(((vid or "").lower(), (pid or "").lower()))
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]
    w = dict(rows[0])
    w["model"] = " / ".join(r["model"] for r in rows)
    ranks = ["Platinum", "Gold", "Silver", "Bronze", "Broken"]
    known = [r["rank"] for r in rows if r.get("rank") in ranks]
    w["rank"] = max(known, key=ranks.index) if known else None      # the most cautious rank
    w["notes"] = list(dict.fromkeys(n for r in rows for n in (r.get("notes") or [])))
    w["fixes"] = list(dict.fromkeys(f for r in rows for f in (r.get("fixes") or [])))
    return w


def wheel_brand(vid: str, pid: str) -> str | None:
    """Brand if this USB device is a wheel base we know, else None."""
    k = identify(vid, pid)
    if k:
        return k["brand"]
    return WHEEL_ONLY_VENDORS.get((vid or "").lower())


def kernel_has_universal_pidff(release: str | None = None, root: str = "/") -> bool:
    """Whether the hid-universal-pidff driver is available. Looks for the module
    itself first (loaded, built in, shipped with the kernel, or installed by
    hand, as the universal-pidff project does on SteamOS), then falls back to the
    kernel version: mainline 6.15+, backported to 6.12.24+, 6.13.12+, 6.14.3+."""
    rel = release or platform.release()
    if release is None or root != "/":
        if any(os.path.exists(os.path.join(root, p)) for p in
               ("sys/module/hid_universal_pidff", "sys/bus/hid/drivers/hid-universal-pidff")):
            return True
        mod_dir = os.path.join(root, "lib/modules", rel)
        builtin = _read(os.path.join(mod_dir, "modules.builtin")) or ""
        if "hid-universal-pidff.ko" in builtin:
            return True
        for pat in ("kernel/drivers/hid/hid-universal-pidff.ko*", "updates/**/hid-universal-pidff.ko*",
                    "extra/**/hid-universal-pidff.ko*"):
            if glob.glob(os.path.join(mod_dir, pat), recursive=True):
                return True
    m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", rel)
    if not m:
        return False
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if (a, b) >= (6, 15):
        return True
    return (a, b) == (6, 12) and c >= 24 or (a, b) == (6, 13) and c >= 12 or (a, b) == (6, 14) and c >= 3


def _read(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return None


def _udev_props(ev_dir: str, root: str = "/") -> dict | None:
    """udev's properties for an input event node (from /run/udev/data), or None."""
    devnum = _read(os.path.join(ev_dir, "dev"))
    if not devnum:
        return None
    data = _read(os.path.join(root, "run/udev/data", f"c{devnum}"))
    if data is None:
        return None
    return dict(l[2:].split("=", 1) for l in data.splitlines() if l.startswith("E:") and "=" in l)


def input_wheels(root: str = "/") -> list[dict]:
    """Wheel bases among the input devices, with whether they accept force feedback
    and whether Linux classes them as a joystick (what Steam and Proton look for)."""
    out = []
    for ev in sorted(glob.glob(os.path.join(root, "sys/class/input/event*"))):
        dev = os.path.join(ev, "device")
        vendor = (_read(os.path.join(dev, "id/vendor")) or "").lower()
        product = (_read(os.path.join(dev, "id/product")) or "").lower()
        brand = wheel_brand(vendor, product)
        if not brand:
            continue
        ff = _read(os.path.join(dev, "capabilities/ff")) or "0"
        props = _udev_props(ev, root)
        out.append({"event": os.path.basename(ev), "name": _read(os.path.join(dev, "name")) or "?",
                    "brand": brand, "vid": vendor, "pid": product, "known": identify(vendor, product),
                    "ffb": any(c not in "0 " for c in ff),
                    "joystick": None if props is None else props.get("ID_INPUT_JOYSTICK") == "1"})
    return out


HWDB_PATH = "/etc/udev/hwdb.d/99-pitwall-wheels.hwdb"


def hwdb_entry(vid: str, pid: str, name: str = "") -> str:
    """A udev hwdb entry that makes Linux class a device as a joystick (and not an
    accelerometer, which 3-axis pedals can be mistaken for)."""
    return (f"# {name or 'wheel'} (added by Pitwall)\n"
            f"id-input:modalias:input:*v{vid.upper()}p{pid.upper()}*\n"
            " ID_INPUT_ACCELEROMETER=0\n ID_INPUT_JOYSTICK=1\n")


def apply_joystick_fix(devs: list[dict], path: str = HWDB_PATH, run=None) -> dict:
    """Add hwdb entries for wheels Linux doesn't class as joysticks, then reload udev.
    Keeps existing entries; safe to run twice."""
    import subprocess
    run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, timeout=30))
    todo = [d for d in devs if d.get("joystick") is False]
    if not todo:
        return {"ok": True, "changed": False, "message": "Nothing to fix: your wheel is already recognised as a game controller."}
    try:
        cur = open(path).read() if os.path.exists(path) else ""
    except OSError:
        cur = ""
    add = "".join(hwdb_entry(d["vid"], d["pid"], d["name"]) for d in todo
                  if f"v{d['vid'].upper()}p{d['pid'].upper()}" not in cur)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if add:
            with open(path, "a") as f:
                f.write(("\n" if cur and not cur.endswith("\n") else "") + add)
        run(["systemd-hwdb", "update"])
        run(["udevadm", "trigger", "--subsystem-match=input"])
    except OSError as e:
        return {"ok": False, "changed": False, "message": f"Couldn't write {path}: {e.strerror}"}
    return {"ok": True, "changed": bool(add),
            "message": "Done. Unplug the wheel and plug it back in, then restart the game."}


def remove_joystick_fix(path: str = HWDB_PATH, run=None) -> bool:
    """Undo apply_joystick_fix (used when Pitwall is uninstalled)."""
    import subprocess
    run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, timeout=30))
    try:
        os.remove(path)
    except FileNotFoundError:
        return False
    except OSError:
        return False
    try:
        run(["systemd-hwdb", "update"])
        run(["udevadm", "trigger", "--subsystem-match=input"])
    except OSError:
        pass
    return True


def sdl_wheel_env(devs: list[dict]) -> str:
    """SDL_JOYSTICK_WHEEL_DEVICES value naming the connected wheels, so SDL (and so
    Steam and Proton) treat them as wheels even if they're not on SDL's built-in list."""
    ids = list(dict.fromkeys(f"0x{d['vid']}/0x{d['pid']}" for d in devs if d.get("vid") and d.get("pid")))
    return ",".join(ids)


def check(hub=None, wheel=None, game: dict | None = None, mangohud_dir: str | None = None) -> list[dict]:
    """Returns [{id, ok, title, detail}] with ok in (True, False, None=info)."""
    res = []

    def add(id_, ok, title, detail=""):
        res.append({"id": id_, "ok": ok, "title": title, "detail": detail})

    # Wheel connected (settings control)
    if wheel:
        add("wheel", True, f"{wheel.name} connected")
    else:
        add("wheel", False, "No wheel found for settings",
            "Pitwall controls MOZA, Logitech, Fanatec and Thrustmaster settings. Check the USB cable and power.")

    # Force feedback available to games
    devs = input_wheels()
    ffb = [d for d in devs if d["ffb"]]
    if ffb:
        add("ffb", True, "Force feedback available", ", ".join(sorted({d["name"] for d in ffb})))
    elif devs:
        known = next((d["known"] for d in devs if d.get("known")), None)
        if known:
            need = known["driver"]
            extra = ""
            if "universal-pidff" in need and not kernel_has_universal_pidff():
                extra = (f" It isn't in your kernel ({platform.release()}). Update SteamOS, or install it from "
                         "Pitwall: Wheel, Force feedback setup.")
            elif known.get("driver_url") and not known.get("in_kernel"):
                extra = " It isn't part of SteamOS; Pitwall can install it: Wheel, Force feedback setup."
            add("ffb", False, f"{known['brand']} {known['model']} found but no force feedback",
                f"It needs {need}.{extra}")
        else:
            add("ffb", False, "Sim racing device found, but no force feedback",
                f"Seen: {', '.join(sorted({d['name'] for d in devs}))}. If one of these is your wheel base, "
                "its kernel driver isn't providing force feedback; check SteamOS is up to date.")
    else:
        add("ffb", None, "No wheel input device seen", "Plug in the wheel, or it may use an unsupported brand.")

    if os.path.isdir("/sys/module/hid_universal_pidff"):
        add("pidff", True, "hid-universal-pidff driver loaded")
    for d in devs:
        k = d.get("known")
        if k:
            notes = k.get("notes") or []
            if isinstance(notes, str):
                notes = [notes]
            add(f"model:{d['event']}", None, f"{k['brand']} {k['model']}: {k.get('rank') or 'untested'} support on Linux",
                " ".join(notes + [f"Source: {WHEEL_DB.get('source', '')}"]))
    not_joy = [d for d in devs if d.get("joystick") is False]
    if not_joy:
        add("joystick", False, "Linux doesn't see " + ", ".join(sorted({d['name'] for d in not_joy})) + " as a game controller",
            "Steam and games may ignore it. Open Wheel, press Fix wheel and pedal detection, then unplug and replug the wheel.")
    elif any(d.get("joystick") for d in devs):
        add("joystick", True, "Wheel and pedals are recognised as game controllers")

    # Telemetry
    if hub:
        st = hub.status()
        if st["receiving"]:
            add("telemetry", True, f"Receiving telemetry from {st['sim']}")
            if st["needs_start_line"]:
                add("start_line", None, "Set a start line to time laps", "This sim doesn't report laps.")
        else:
            errs = [s["error"] for s in st["sources"] if s.get("error")]
            add("telemetry", None if not game else False, "No telemetry right now",
                "; ".join(errs) if errs else "Start driving, and check the game's telemetry output is switched on.")

    # Game-specific
    if game:
        t = game.get("telemetry", {})
        files = game.get("shm_files") or []
        if t.get("needs_bridge") and files:
            ok = any(os.path.exists(os.path.join("/dev/shm", f)) for f in files)
            how = ("Use Game guide → Set up telemetry bridge, then restart the game."
                   if game.get("bridge_auto") else "This game needs a shared-memory bridge running with it.")
            add("bridge", ok, "Telemetry bridge running" if ok else "Telemetry bridge not running", "" if ok else how)
        if game.get("status") == "broken":
            add("compat", False, f"{game['name']} doesn't run on SteamOS", (game.get("install") or [""])[0])

    # MangoHud for benchmarks
    if shutil.which("mangohud"):
        add("mangohud", True, "MangoHud available for benchmarks")
    else:
        add("mangohud", None, "MangoHud not found", "Performance benchmarks need MangoHud.")
    return res


SDL_VAR = "SDL_JOYSTICK_WHEEL_DEVICES"


def env_launch_options(current: str, var: str, value: str, enable: bool) -> str:
    """Add, update or remove VAR=value at the start of a game's launch options,
    keeping everything else the user (or Pitwall's bridge) set."""
    cur = (current or "").strip()
    cur = re.sub(rf"(^|\s){re.escape(var)}=\S+\s*", r"\1", cur).strip()
    if not enable or not value:
        return "" if cur == "%command%" else cur
    if "%command%" not in cur:
        cur = f"%command% {cur}".strip()
    return f"{var}={value} {cur}"


def sdl_launch_options(current: str, value: str, enable: bool) -> str:
    return env_launch_options(current, SDL_VAR, value, enable)


def ff_caps(event: str, root: str = "/") -> str:
    return _read(os.path.join(root, "sys/class/input", event, "device/capabilities/ff")) or "0"
