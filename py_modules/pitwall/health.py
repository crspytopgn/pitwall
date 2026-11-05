"""Pre-race health checks: is everything in place before you drive?"""

from __future__ import annotations

import glob
import os
import shutil

WHEEL_VENDORS = {"346e": "MOZA", "046d": "Logitech", "0eb7": "Fanatec", "044f": "Thrustmaster",
                 "0483": "Simagic (or other STM32 device)", "3416": "Cammus", "16d0": "Simucube"}


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
        out.append({"event": os.path.basename(ev), "name": name, "brand": WHEEL_VENDORS[vendor],
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
        add("ffb", False, "Wheel found but no force feedback",
            "The kernel driver isn't providing FFB. MOZA needs hid-universal-pidff "
            "(in mainline Linux since 6.15). Check SteamOS is up to date.")
    else:
        add("ffb", None, "No wheel input device seen", "Plug in the wheel, or it may use an unsupported brand.")

    if os.path.isdir("/sys/module/hid_universal_pidff"):
        add("pidff", True, "hid-universal-pidff driver loaded")

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
        if t.get("needs_bridge") and t.get("adapter") == "ac_shm":
            ok = os.path.exists("/dev/shm/acpmf_physics")
            add("bridge", ok, "Shared-memory bridge running" if ok else "Shared-memory bridge not running",
                "" if ok else "Telemetry for this game needs simshmbridge or winecarte running with it.")
        if game.get("status") == "broken":
            add("compat", False, f"{game['name']} doesn't run on SteamOS", (game.get("install") or [""])[0])

    # MangoHud for benchmarks
    if shutil.which("mangohud"):
        add("mangohud", True, "MangoHud available for benchmarks")
    else:
        add("mangohud", None, "MangoHud not found", "Performance benchmarks need MangoHud.")
    return res
