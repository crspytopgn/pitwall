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

WHEEL_VENDORS = {w["vid"]: w["brand"] for w in WHEEL_DB["wheels"] if w.get("vid")}
WHEEL_VENDORS["0483"] = "Simagic / VRS"        # shared STM32 vendor id


def identify(vid: str, pid: str) -> dict | None:
    """Look a wheel up in the community-tested support table."""
    for w in WHEEL_DB["wheels"]:
        if w.get("vid") == vid and w.get("pid") == pid:
            return w
    return None


def kernel_has_universal_pidff(release: str | None = None) -> bool:
    """hid-universal-pidff: Linux 6.15+, backported to 6.12.24+, 6.13.12+, 6.14.3+."""
    m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", release or platform.release())
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


def input_wheels() -> list[dict]:
    """Input devices from known wheel vendors, with whether they accept force feedback."""
    out = []
    for ev in sorted(glob.glob("/sys/class/input/event*")):
        dev = os.path.join(ev, "device")
        vendor = (_read(os.path.join(dev, "id/vendor")) or "").lower()
        if vendor not in WHEEL_VENDORS:
            continue
        ff = _read(os.path.join(dev, "capabilities/ff")) or "0"
        name = _read(os.path.join(dev, "name")) or "?"
        product = (_read(os.path.join(dev, "id/product")) or "").lower()
        out.append({"event": os.path.basename(ev), "name": name, "brand": WHEEL_VENDORS[vendor],
                    "vid": vendor, "pid": product, "known": identify(vendor, product),
                    "ffb": any(c not in "0 " for c in ff)})
    return out


def check(hub=None, wheel=None, game: dict | None = None, mangohud_dir: str | None = None) -> list[dict]:
    """Returns [{id, ok, title, detail}] with ok in (True, False, None=info)."""
    res = []

    def add(id_, ok, title, detail=""):
        res.append({"id": id_, "ok": ok, "title": title, "detail": detail})

    # Wheel connected (settings control)
    if wheel:
        add("wheel", True, f"{wheel.name} connected")
    else:
        add("wheel", False, "No supported wheel found for settings",
            "MOZA and Logitech are supported for settings. Check the USB cable and power.")

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
                extra = f" Your kernel ({platform.release()}) is older than that: update SteamOS."
            add("ffb", False, f"{known['brand']} {known['model']} found but no force feedback",
                f"It needs {need}.{extra}")
        else:
            add("ffb", False, "Wheel found but no force feedback",
                "The kernel driver isn't providing FFB. Check SteamOS is up to date.")
    else:
        add("ffb", None, "No wheel input device seen", "Plug in the wheel, or it may use an unsupported brand.")

    if os.path.isdir("/sys/module/hid_universal_pidff"):
        add("pidff", True, "hid-universal-pidff driver loaded")
    for d in devs:
        k = d.get("known")
        if k:
            add(f"model:{d['event']}", None, f"{k['brand']} {k['model']}: {k.get('rank') or 'untested'} support on Linux",
                (k.get("notes") or "") + f" Source: {WHEEL_DB.get('source', '')}")

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
