"""
Wheel drivers. Every driver exposes the same small interface so the UI,
profiles and FFB tools don't care which brand is plugged in:

    detect() -> bool
    name, brand -> str
    settings() -> {key: {"min","max","step","label","suffix","toggle"}}
    read_all() -> {key: value} | None
    write({key: value}) -> bool
    center() -> bool           (MOZA only for now)
    leds(mask) / leds_supported (MOZA wheels with rev lights)

MOZA talks to the base over its serial protocol (from Boxflat). Logitech,
Fanatec and Thrustmaster are driven through the sysfs files their Linux
kernel drivers expose:

- Logitech: hid-logitech (mainline: range) or new-lg4ff (adds gain, autocenter,
  spring/damper/friction) https://github.com/berarma/new-lg4ff
- Fanatec: hid-fanatecff https://github.com/gotzl/hid-fanatecff
  (range plus the base's tuning menu under /sys/class/ftec_tuning)
- Thrustmaster: hid-tmff2 https://github.com/Kimplul/hid-tmff2
  (range, gain, spring/damper/friction levels)

Only settings whose files actually exist are offered, so the same code works
with mainline and community drivers.
"""

from __future__ import annotations

import glob
import os

from .moza import MozaBase, SETTINGS as MOZA_SETTINGS, base_model

_LABELS = {
    "rotation": ("Rotation", 10, "°"), "ffb_strength": ("Game FFB strength", 1, "%"),
    "torque": ("Base torque output", 5, "%"), "road_sensitivity": ("Road sensitivity", 1, ""),
    "damper": ("Damper", 1, "%"), "friction": ("Friction", 1, "%"), "inertia": ("Natural inertia", 10, "%"),
    "speed_damping": ("Speed-dependent damping", 1, "%"), "speed_damping_point": ("Speed damping starts at", 10, " km/h"),
    "spring": ("Spring", 1, "%"), "speed": ("Max wheel speed", 1, "%"), "ffb_enabled": ("Force feedback", 1, ""),
}


def _def(key, lo, hi, label=None, step=None, suffix=None, toggle=False):
    l, s, u = _LABELS.get(key, (key, 1, ""))
    return {"min": lo, "max": hi, "step": step or s, "label": label or l, "suffix": u if suffix is None else suffix,
            "toggle": toggle}


class MozaDriver:
    brand = "MOZA"
    leds_supported = True

    def __init__(self, logger=None, path_override=None):
        self.dev = MozaBase(logger=logger, path_override=path_override)

    @property
    def model(self):
        return base_model(self.dev.path)

    @property
    def name(self):
        return f"MOZA {self.model}" if self.model else "MOZA"

    def detect(self) -> bool:
        return self.dev.connected()

    def settings(self) -> dict:
        return {k: _def(k, s.lo, s.hi, toggle=(k == "ffb_enabled")) for k, s in MOZA_SETTINGS.items()}

    def read_all(self):
        return self.dev.read_all()

    def write(self, values: dict) -> bool:
        return self.dev.write(values)

    def center(self) -> bool:
        return self.dev.calibrate_center()

    def leds_begin(self) -> bool:
        return self.dev.set_led_telemetry_mode(True)

    def leds_end(self) -> bool:
        return self.dev.set_led_telemetry_mode(False)

    def leds(self, mask: int) -> bool:
        return self.dev.send_rpm_leds(mask)

    def close(self):
        self.dev.close()

    @property
    def error(self):
        return self.dev.last_error


class SysfsDriver:
    """A wheel controlled through files its kernel driver exposes."""
    leds_supported = False
    model = None
    brand = "?"
    # key -> (glob, lo, hi, ui_to_file, file_to_ui, extra def kwargs)
    ATTRS: dict = {}

    def __init__(self):
        self.error = None

    @property
    def name(self):
        return self.brand

    def _path(self, key):
        hits = sorted(glob.glob(self.ATTRS[key][0]))
        return hits[0] if hits else None

    def available(self):
        return [k for k in self.ATTRS if self._path(k)]

    def detect(self) -> bool:
        return "rotation" in self.available()

    def settings(self):
        out = {}
        for k in self.available():
            _g, lo, hi, _to, _from, kw = self.ATTRS[k]
            out[k] = _def(k, lo, hi, **kw)
        return out

    def read_all(self):
        vals = {}
        for k in self.available():
            try:
                with open(self._path(k)) as f:
                    raw = f.read().strip().split()[0]
                vals[k] = self.ATTRS[k][4](int(raw, 0))
            except (OSError, ValueError, IndexError, TypeError):
                continue
        return vals or None

    def write(self, values):
        ok = True
        for k, v in values.items():
            if k not in self.ATTRS or v is None:
                continue
            p = self._path(k)
            if not p:
                continue
            _g, lo, hi, to_file, _f, _kw = self.ATTRS[k]
            try:
                with open(p, "w") as f:
                    f.write(str(int(to_file(max(lo, min(hi, float(v)))))))
            except OSError as e:
                self.error = f"{k}: {e.strerror}"
                ok = False
        return ok

    def center(self):
        return False

    def close(self):
        pass


_id = (lambda v: round(v), lambda d: d)
_pct16 = (lambda v: round(v * 65535 / 100), lambda d: round(d * 100 / 65535))


class LogitechDriver(SysfsDriver):
    brand = "Logitech"
    _B = "/sys/bus/hid/drivers/logitech*/*/"
    ATTRS = {
        "rotation": (_B + "range", 40, 900, *_id, {}),
        "ffb_strength": (_B + "gain", 0, 100, *_pct16, {"label": "Overall FFB gain"}),
        "autocenter": (_B + "autocenter", 0, 100, *_pct16, {"label": "Autocenter spring", "suffix": "%"}),
        "spring": (_B + "spring_level", 0, 100, *_id, {}),
        "damper": (_B + "damper_level", 0, 100, *_id, {}),
        "friction": (_B + "friction_level", 0, 100, *_id, {}),
    }


class ThrustmasterDriver(SysfsDriver):
    brand = "Thrustmaster"
    _B = "/sys/bus/hid/drivers/tmff2/*/"
    ATTRS = {
        "rotation": (_B + "range", 40, 1080, *_id, {}),
        "ffb_strength": (_B + "gain", 0, 100, *_pct16, {"label": "Overall FFB gain"}),
        "spring": (_B + "spring_level", 0, 100, *_id, {}),
        "damper": (_B + "damper_level", 0, 100, *_id, {}),
        "friction": (_B + "friction_level", 0, 100, *_id, {}),
    }


class FanatecDriver(SysfsDriver):
    brand = "Fanatec"
    _T = "/sys/class/ftec_tuning/*/"
    ATTRS = {
        "rotation": ("/sys/bus/hid/drivers/fanatec/*/range", 90, 2530, *_id, {}),
        "ffb_strength": (_T + "FF", 0, 100, *_id, {"label": "FFB strength (FF)"}),
        "force_effect": (_T + "FOR", 0, 120, *_id, {"label": "Force effect (FOR)", "suffix": "%"}),
        "spring": (_T + "SPR", 0, 120, *_id, {"label": "Spring (SPR)"}),
        "damper": (_T + "DPR", 0, 120, *_id, {"label": "Damper (DPR)"}),
        "natural_damper": (_T + "NDP", 0, 100, *_id, {"label": "Natural damper (NDP)", "suffix": ""}),
        "friction": (_T + "NFR", 0, 100, *_id, {"label": "Natural friction (NFR)", "suffix": ""}),
        "interpolation": (_T + "INT", 0, 20, *_id, {"label": "FFB interpolation (INT)", "suffix": ""}),
    }


SYSFS_DRIVERS = [LogitechDriver, FanatecDriver, ThrustmasterDriver]


def detect_wheel(logger=None, moza_tty=None):
    """Return the first connected, controllable wheel driver, or None."""
    moza = MozaDriver(logger, moza_tty)
    if moza.detect():
        return moza
    moza.close()
    for cls in SYSFS_DRIVERS:
        d = cls()
        if d.detect():
            return d
    return None
