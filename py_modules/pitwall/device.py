"""
Device profile and one-tap auto setup.

Works out what Pitwall is running on (Steam Machine, Steam Deck or another
PC), the wheel model, and from those picks:

- the best starting wheel preset (MOZA's own per-base recommendation)
- a frame-rate target for the performance check
- per-game steps from the game guide

Game graphics settings aren't written automatically: every game stores them
differently and none have been verified yet, so Pitwall measures performance
and says what to change instead.
"""

from __future__ import annotations

import glob
import os


def _read(p, limit=200):
    try:
        with open(p, errors="replace") as f:
            return f.read(limit).strip()
    except OSError:
        return None


def mem_gb() -> float | None:
    txt = _read("/proc/meminfo", 400) or ""
    for line in txt.splitlines():
        if line.startswith("MemTotal:"):
            return round(int(line.split()[1]) / 1024 / 1024, 1)
    return None


def gpus() -> list[dict]:
    out = []
    for card in sorted(glob.glob("/sys/class/drm/card[0-9]")):
        dev = os.path.join(card, "device")
        vendor = (_read(os.path.join(dev, "vendor")) or "").lower()
        vram = _read(os.path.join(dev, "mem_info_vram_total"))
        out.append({"card": os.path.basename(card),
                    "vendor": {"0x1002": "AMD", "0x10de": "NVIDIA", "0x8086": "Intel"}.get(vendor, vendor or "?"),
                    "vram_gb": round(int(vram) / 1024 ** 3, 1) if vram and vram.isdigit() else None})
    return out


def detect() -> dict:
    product = _read("/sys/class/dmi/id/product_name")
    vendor = _read("/sys/class/dmi/id/sys_vendor")
    os_name = None
    for line in (_read("/etc/os-release", 2000) or "").splitlines():
        if line.startswith("PRETTY_NAME="):
            os_name = line.split("=", 1)[1].strip('"')
    kind = "pc"
    p = (product or "").lower()
    if p in ("jupiter", "galileo"):
        kind = "steam_deck"           # Valve's Steam Deck LCD / OLED board names
    elif "valve" in (vendor or "").lower():
        kind = "steam_machine"        # other Valve hardware: treat as the TV box
    g = gpus()
    return {"kind": kind, "product": product, "vendor": vendor, "os": os_name,
            "cpus": os.cpu_count(), "ram_gb": mem_gb(), "gpus": g,
            "vram_gb": max((x["vram_gb"] or 0) for x in g) if g else None}


def default_target_fps(dev: dict) -> int:
    # Steam Deck's own screen is 60 Hz (OLED up to 90). TVs are usually 60 Hz;
    # people with 120 Hz TVs can raise it.
    return 60


def plan(dev: dict, wheel, games: list[dict], preset_for_base) -> dict:
    """What auto setup will do, before doing it."""
    steps = []
    preset = None
    if wheel is not None:
        model = getattr(wheel, "model", None)
        if wheel.brand == "MOZA":
            preset = preset_for_base(model)
            steps.append({"id": "wheel", "title": f"Apply {'MOZA ' + model if model else 'MOZA'} settings",
                          "detail": f"Starting preset: {preset}. You can fine-tune afterwards with the feel tuner."})
        else:
            preset = "pure"
            steps.append({"id": "wheel", "title": f"Apply clean {wheel.brand} settings",
                          "detail": "No added spring or damper, so you feel what the sim calculates."})
    else:
        steps.append({"id": "wheel", "title": "No wheel to set up", "detail": "Plug in the wheel and run auto setup again."})
    fps = default_target_fps(dev)
    steps.append({"id": "fps", "title": f"Set performance target to {fps} FPS",
                  "detail": "Change it on the Performance page if your TV runs at 120 Hz."})
    installed = [g for g in games if g.get("installed")]
    for g in installed:
        if g["status"] == "broken":
            steps.append({"id": f"warn:{g['id']}", "title": f"{g['name']} won't run on SteamOS", "detail": "See the game guide."})
        elif g.get("auto_setup") or g.get("bridge_auto"):
            steps.append({"id": f"game:{g['id']}", "title": f"Telemetry for {g['name']}",
                          "detail": "Open its game guide page and press the setup button."})
    return {"device": dev, "preset": preset, "target_fps": fps, "steps": steps}
