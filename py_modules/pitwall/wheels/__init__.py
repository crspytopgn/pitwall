"""
Wheel drivers. Each driver exposes the same small interface so the UI and
profiles don't care which brand is plugged in:

    detect() -> bool
    name -> str
    settings() -> {key: {"min","max","step","label"}}   # what this wheel supports
    read_all() -> {key: value} | None
    write({key: value}) -> bool
    center() -> bool                                     # optional

Supported:
- MOZA Racing (all bases Boxflat supports): full settings over its serial protocol
- Logitech (G29/G920/G923 and older, via the kernel's hid-logitech driver): rotation

Planned: Fanatec (hid-fanatecff), Thrustmaster (hid-tmff2), Simagic, Cammus.
"""

from __future__ import annotations

import glob
import os

from .moza import MozaBase, SETTINGS as MOZA_SETTINGS

_LABELS = {
    "rotation": ("Rotation", 10, "°"), "ffb_strength": ("Game FFB strength", 1, "%"),
    "torque": ("Base torque output", 5, "%"), "road_sensitivity": ("Road sensitivity", 1, ""),
    "damper": ("Damper", 1, "%"), "friction": ("Friction", 1, "%"), "inertia": ("Natural inertia", 10, "%"),
    "speed_damping": ("Speed-dependent damping", 1, "%"), "speed_damping_point": ("Speed damping starts at", 10, " km/h"),
    "spring": ("Spring", 1, "%"), "speed": ("Max wheel speed", 1, "%"), "ffb_enabled": ("Force feedback", 1, ""),
}


class MozaDriver:
    brand = "MOZA"

    def __init__(self, logger=None, path_override=None):
        self.dev = MozaBase(logger=logger, path_override=path_override)

    @property
    def name(self):
        return f"MOZA ({os.path.basename(self.dev.path)})" if self.dev.path else "MOZA"

    def detect(self) -> bool:
        return self.dev.connected()

    def settings(self) -> dict:
        return {k: {"min": s.lo, "max": s.hi, "step": _LABELS[k][1], "label": _LABELS[k][0],
                    "suffix": _LABELS[k][2], "toggle": k == "ffb_enabled"} for k, s in MOZA_SETTINGS.items()}

    def read_all(self):
        return self.dev.read_all()

    def write(self, values: dict) -> bool:
        return self.dev.write(values)

    def center(self) -> bool:
        return self.dev.calibrate_center()

    def close(self):
        self.dev.close()

    @property
    def error(self):
        return self.dev.last_error


class LogitechDriver:
    """Logitech wheels expose rotation as a sysfs 'range' file (hid-lg4ff)."""
    brand = "Logitech"
    name = "Logitech"
    error = None

    def _range_file(self):
        for p in glob.glob("/sys/bus/hid/drivers/logitech/*/range"):
            return p
        return None

    def detect(self) -> bool:
        return self._range_file() is not None

    def settings(self):
        return {"rotation": {"min": 40, "max": 900, "step": 10, "label": "Rotation", "suffix": "°", "toggle": False}}

    def read_all(self):
        p = self._range_file()
        if not p:
            return None
        try:
            with open(p) as f:
                return {"rotation": int(f.read().strip())}
        except (OSError, ValueError):
            return None

    def write(self, values):
        p = self._range_file()
        if not p or "rotation" not in values:
            return bool(p)
        try:
            with open(p, "w") as f:
                f.write(str(int(max(40, min(900, values["rotation"])))))
            return True
        except OSError as e:
            self.error = str(e)
            return False

    def center(self):
        return False

    def close(self):
        pass


def detect_wheel(logger=None, moza_tty=None):
    """Return the first connected wheel driver, or None."""
    moza = MozaDriver(logger, moza_tty)
    if moza.detect():
        return moza
    moza.close()
    lg = LogitechDriver()
    if lg.detect():
        return lg
    return None
