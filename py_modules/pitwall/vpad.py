"""Use the wheel's buttons in Steam's menus.

Steam's interface follows gamepads, and a wheel isn't one. While no game is
running, Pitwall creates a virtual Xbox 360 controller with Linux's uinput
and presses its buttons when you press the wheel buttons mapped to them.
When a game starts, the virtual controller is removed, so games only ever see
your wheel and there are no doubled inputs.

Struct layouts and ioctl numbers checked with gcc against <linux/uinput.h> on
x86_64: struct uinput_setup is 92 bytes (name at 8, ff_effects_max at 88),
struct uinput_abs_setup is 28 bytes.
"""

from __future__ import annotations

import fcntl
import os
import struct
import threading
import time

UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
UI_DEV_SETUP, UI_ABS_SETUP = 0x405C5503, 0x401C5504
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045567
EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
BUS_USB = 0x03
ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ, ABS_HAT0X, ABS_HAT0Y = 0, 1, 2, 3, 4, 5, 0x10, 0x11

BTN = {"a": 0x130, "b": 0x131, "x": 0x133, "y": 0x134, "lb": 0x136, "rb": 0x137,
       "view": 0x13A, "menu": 0x13B, "steam": 0x13C, "ls": 0x13D, "rs": 0x13E}

# What each action does in Steam (Gaming Mode / Big Picture).
ACTIONS = [
    ("a", "Select (A)"), ("b", "Back (B)"), ("x", "X"), ("y", "Y"),
    ("up", "Up"), ("down", "Down"), ("left", "Left"), ("right", "Right"),
    ("steam", "Steam menu"), ("qam", "Quick Access menu (…)"),
    ("lb", "Previous tab (LB)"), ("rb", "Next tab (RB)"), ("view", "View"), ("menu", "Menu"),
]
ACTION_LABELS = dict(ACTIONS)
DPAD = {"up": (ABS_HAT0Y, -1), "down": (ABS_HAT0Y, 1), "left": (ABS_HAT0X, -1), "right": (ABS_HAT0X, 1)}


def default_map(dev: dict) -> dict:
    """A starting layout for a wheel: its D-pad for navigation, its first
    buttons for Select, Back, the Steam menu and Quick Access. Shown in the UI
    and changeable by pressing the button you want."""
    m = {}
    if dev.get("hats"):
        n = dev["hats"][0]
        for d in ("up", "down", "left", "right"):
            m[d] = f"{dev['id']}/hat{n}-{d}"
    order = ["a", "b", "steam", "qam", "x", "y", "lb", "rb", "view", "menu"]
    for action, code in zip(order, dev.get("buttons", [])):
        m[action] = f"{dev['id']}/b{code}"
    return m


class VirtualPad:
    NAME = b"Pitwall wheel navigation"

    def __init__(self, path: str = "/dev/uinput", opener=None, ioctl=None, write=None):
        self.path = path
        self._open = opener or (lambda p: os.open(p, os.O_WRONLY | os.O_NONBLOCK))
        self._ioctl = ioctl or fcntl.ioctl
        self._write = write or os.write
        self.fd = None

    def create(self):
        fd = self._open(self.path)
        try:
            for ev in (EV_KEY, EV_ABS, EV_SYN):
                self._ioctl(fd, UI_SET_EVBIT, ev)
            for code in BTN.values():
                self._ioctl(fd, UI_SET_KEYBIT, code)
            axes = {ABS_X: (-32768, 32767), ABS_Y: (-32768, 32767), ABS_RX: (-32768, 32767), ABS_RY: (-32768, 32767),
                    ABS_Z: (0, 255), ABS_RZ: (0, 255), ABS_HAT0X: (-1, 1), ABS_HAT0Y: (-1, 1)}
            for code, (lo, hi) in axes.items():
                self._ioctl(fd, UI_SET_ABSBIT, code)
                self._ioctl(fd, UI_ABS_SETUP, struct.pack("<HHiiiiii", code, 0, 0, lo, hi, 0, 0, 0))
            # Looks like an Xbox 360 controller so Steam knows the layout.
            setup = struct.pack("<HHHH80sI", BUS_USB, 0x045E, 0x028E, 0x0114, self.NAME, 0)
            self._ioctl(fd, UI_DEV_SETUP, setup)
            self._ioctl(fd, UI_DEV_CREATE)
        except OSError:
            os.close(fd) if isinstance(fd, int) and fd > 2 else None
            raise
        self.fd = fd

    def _ev(self, typ, code, value):
        self._write(self.fd, struct.pack("<qqHHi", 0, 0, typ, code, value))

    def emit(self, events: list[tuple]):
        if self.fd is None:
            return
        for typ, code, value in events:
            self._ev(typ, code, value)
        self._ev(EV_SYN, 0, 0)

    def action(self, action: str, pressed: bool):
        v = 1 if pressed else 0
        if action in BTN:
            self.emit([(EV_KEY, BTN[action], v)])
        elif action in DPAD:
            axis, val = DPAD[action]
            self.emit([(EV_ABS, axis, val if pressed else 0)])
        elif action == "qam":
            # Steam opens Quick Access with Steam (Guide) + A on Xbox controllers.
            if pressed:
                self.emit([(EV_KEY, BTN["steam"], 1)])
                self.emit([(EV_KEY, BTN["a"], 1)])
            else:
                self.emit([(EV_KEY, BTN["a"], 0)])
                self.emit([(EV_KEY, BTN["steam"], 0)])

    def destroy(self):
        if self.fd is None:
            return
        try:
            self._ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except (OSError, TypeError):
            pass
        self.fd = None


class NavBridge:
    """Wheel button presses -> virtual controller, only while enabled and no game runs."""

    def __init__(self, pad_factory=VirtualPad, log=None):
        self.pad_factory = pad_factory
        self.log = log
        self.mapping: dict[str, str] = {}        # action -> control
        self.enabled = False
        self.in_game = False
        self.pad = None
        self.error = None
        self.lock = threading.Lock()
        self._held: set[str] = set()

    def configure(self, enabled: bool, mapping: dict):
        with self.lock:
            self.enabled = bool(enabled)
            self.mapping = dict(mapping or {})
        self._sync()

    def set_in_game(self, in_game: bool):
        with self.lock:
            self.in_game = bool(in_game)
        self._sync()

    @property
    def active(self) -> bool:
        return self.pad is not None

    def _sync(self):
        with self.lock:
            want = self.enabled and not self.in_game and bool(self.mapping)
            if want and self.pad is None:
                try:
                    p = self.pad_factory()
                    p.create()
                    self.pad, self.error = p, None
                except OSError as e:
                    self.error = f"Couldn't create the virtual controller: {e.strerror or e}"
                    if self.log:
                        self.log.warning(self.error)
            elif not want and self.pad is not None:
                self._release_all()
                self.pad.destroy()
                self.pad = None

    def _release_all(self):
        for a in list(self._held):
            try:
                self.pad.action(a, False)
            except OSError:
                pass
        self._held.clear()

    def on_button(self, control: str, pressed: bool, _dev=None):
        with self.lock:
            if self.pad is None:
                return
            for action, c in self.mapping.items():
                if c == control:
                    try:
                        self.pad.action(action, pressed)
                    except OSError:
                        continue
                    (self._held.add if pressed else self._held.discard)(action)

    def close(self):
        with self.lock:
            self.enabled = False
        self._sync()


def wait(s: float):
    time.sleep(s)
