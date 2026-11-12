"""Wheel buttons: read them, number them the way games do, and learn them.

Reads the wheel's evdev devices without grabbing them (games and Steam still
see every press). Buttons are numbered in the order SDL uses on Linux, which
is also how Proton presents them to games: key codes from BTN_JOYSTICK up to
KEY_MAX first, then BTN_MISC up to BTN_JOYSTICK. "Button 1" is the first.

A control is identified across reboots by the device's USB IDs plus the key
code or hat direction, e.g. "346e:0005/b288" or "346e:0005/hat0-up".
"""

from __future__ import annotations

import glob
import os
import select
import struct
import threading
import time
from collections import deque

EV_KEY, EV_ABS = 0x01, 0x03
BTN_MISC, BTN_JOYSTICK, KEY_MAX = 0x100, 0x120, 0x2FF
ABS_HAT0X = 0x10
EVENT = struct.Struct("<qqHHi")          # struct input_event on 64-bit


def _read(p: str) -> str | None:
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return None


def parse_bits(hexwords: str | None) -> set[int]:
    """sysfs capability masks: space-separated hex words, most significant first."""
    bits = 0
    for w in (hexwords or "0").split():
        bits = (bits << 64) | int(w, 16)
    return {i for i in range(bits.bit_length()) if bits >> i & 1}


def button_order(codes: set[int]) -> list[int]:
    """Joystick buttons in SDL/Proton order."""
    return [c for c in range(BTN_JOYSTICK, KEY_MAX + 1) if c in codes] + \
           [c for c in range(BTN_MISC, BTN_JOYSTICK) if c in codes]


def hats(abs_codes: set[int]) -> list[int]:
    """Hat numbers (0-3) the device has, from ABS_HAT0X..ABS_HAT3Y."""
    return sorted({(c - ABS_HAT0X) // 2 for c in abs_codes if ABS_HAT0X <= c <= 0x17})


def device_info(event: str, root: str = "/") -> dict | None:
    base = os.path.join(root, "sys/class/input", event, "device")
    vid = (_read(os.path.join(base, "id/vendor")) or "").lower()
    pid = (_read(os.path.join(base, "id/product")) or "").lower()
    if not vid:
        return None
    keys = parse_bits(_read(os.path.join(base, "capabilities/key")))
    order = button_order(keys)
    hs = hats(parse_bits(_read(os.path.join(base, "capabilities/abs"))))
    return {"event": event, "id": f"{vid}:{pid}", "name": _read(os.path.join(base, "name")) or event,
            "buttons": order, "hats": hs}


def control_label(control: str, devices: dict[str, dict]) -> str:
    """'346e:0005/b289' -> 'Button 2 (MOZA R3 Base)'."""
    dev_id, _, part = control.partition("/")
    dev = devices.get(dev_id)
    where = f" ({dev['name']})" if dev and len(devices) > 1 else ""
    if part.startswith("b") and part[1:].isdigit():
        code = int(part[1:])
        if dev and code in dev["buttons"]:
            return f"Button {dev['buttons'].index(code) + 1}{where}"
        return f"Button code {code}{where}"
    if part.startswith("hat"):
        n, _, d = part[3:].partition("-")
        return f"D-pad {d}" + (f" {int(n) + 1}" if n not in ("", "0") else "") + where
    return control


class ButtonWatcher:
    """Background reader for every wheel/pedal/shifter input device.

    listeners get (control, pressed, device) for each press and release.
    """

    def __init__(self, find_devices, root: str = "/", rescan_s: float = 3.0):
        self.find_devices = find_devices          # -> list of event names (e.g. from health.input_wheels)
        self.root = root
        self.rescan_s = rescan_s
        self.listeners: list = []
        self.device_listeners: list = []          # called (no args) when the set of devices changes
        self.devices: dict[str, dict] = {}        # by id
        self.recent: deque = deque(maxlen=20)
        self.pressed: set[str] = set()
        self._fds: dict[int, dict] = {}
        self._hat: dict[tuple, int] = {}
        self._learn: dict | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        if not self._thread:
            self._thread = threading.Thread(target=self._run, name="pitwall-buttons", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        for fd in list(self._fds):
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds.clear()

    # ---------------------------------------------------------------- learning
    def learn(self, timeout: float = 15.0) -> dict:
        """Arm: the next press anywhere is captured. Poll learned()."""
        with self._lock:
            self._learn = {"until": time.monotonic() + timeout, "control": None}
        return {"ok": True}

    def learned(self) -> dict:
        with self._lock:
            j = self._learn
            if not j:
                return {"state": "idle"}
            if j["control"]:
                self._learn = None
                return {"state": "done", "control": j["control"], "label": control_label(j["control"], self.devices)}
            if time.monotonic() > j["until"]:
                self._learn = None
                return {"state": "timeout"}
            return {"state": "waiting"}

    def snapshot_devices(self) -> dict:
        with self._lock:
            return dict(self.devices)

    def snapshot(self) -> dict:
        with self._lock:
            return {"devices": list(self.devices.values()), "pressed": sorted(self.pressed),
                    "recent": list(self.recent)}

    # ---------------------------------------------------------------- reading
    def _rescan(self):
        want = set(self.find_devices() or [])
        have = {d["event"] for d in self._fds.values()}
        for fd, d in list(self._fds.items()):
            if d["event"] not in want:
                os.close(fd)
                del self._fds[fd]
        for ev in want - have:
            info = device_info(ev, self.root)
            if not info or not (info["buttons"] or info["hats"]):
                continue
            try:
                fd = os.open(os.path.join(self.root, "dev/input", ev), os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            self._fds[fd] = info
        with self._lock:
            before = set(self.devices)
            self.devices = {d["id"]: d for d in self._fds.values()}
            changed = before != set(self.devices)
        if changed:
            for cb in list(self.device_listeners):
                try:
                    cb()
                except Exception:
                    import logging
                    logging.getLogger("pitwall").exception("Device listener failed")

    def _emit(self, control: str, pressed: bool, dev: dict):
        with self._lock:
            if pressed:
                self.pressed.add(control)
                self.recent.appendleft({"control": control, "label": control_label(control, self.devices), "t": time.time()})
                if self._learn and not self._learn["control"]:
                    self._learn["control"] = control
            else:
                self.pressed.discard(control)
        for cb in list(self.listeners):
            try:
                cb(control, pressed, dev)
            except Exception:
                import logging
                logging.getLogger("pitwall").exception("Button listener failed")

    def handle(self, dev: dict, data: bytes):
        """Process raw input_event bytes from one device (also used by tests)."""
        for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
            _s, _us, typ, code, value = EVENT.unpack_from(data, off)
            if typ == EV_KEY and code in dev["buttons"] and value in (0, 1):
                self._emit(f"{dev['id']}/b{code}", value == 1, dev)
            elif typ == EV_ABS and ABS_HAT0X <= code <= 0x17:
                n, axis = (code - ABS_HAT0X) // 2, (code - ABS_HAT0X) % 2
                prev = self._hat.get((dev["id"], n, axis), 0)
                value = (value > 0) - (value < 0)
                if value == prev:
                    continue
                names = ("left", "right") if axis == 0 else ("up", "down")
                if prev:
                    self._emit(f"{dev['id']}/hat{n}-{names[prev > 0]}", False, dev)
                if value:
                    self._emit(f"{dev['id']}/hat{n}-{names[value > 0]}", True, dev)
                self._hat[(dev["id"], n, axis)] = value

    def _run(self):
        last_scan = 0.0
        while not self._stop.is_set():
            if time.monotonic() - last_scan > self.rescan_s:
                try:
                    self._rescan()
                except Exception:
                    pass
                last_scan = time.monotonic()
            if not self._fds:
                self._stop.wait(self.rescan_s)
                continue
            try:
                r, _, _ = select.select(list(self._fds), [], [], 1.0)
            except (OSError, ValueError):
                self._fds.clear()
                continue
            for fd in r:
                dev = self._fds.get(fd)
                try:
                    data = os.read(fd, EVENT.size * 64)
                except BlockingIOError:
                    continue
                except OSError:                      # unplugged
                    os.close(fd)
                    self._fds.pop(fd, None)
                    continue
                if dev and data:
                    self.handle(dev, data)


def available(root: str = "/") -> list[str]:
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(root, "dev/input/event*")))
