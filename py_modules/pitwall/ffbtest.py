"""Force feedback test through the Linux input layer.

Plays a gentle constant force to the left, then to the right, on the wheel's
evdev device: the same interface games use through Proton/SDL. If the wheel
moves, the kernel driver and the wheel are working, and any remaining problem
is in the game or Proton. Also lists the effects the driver supports.

Struct layout and ioctl numbers checked with gcc against <linux/input.h> on
x86_64: struct ff_effect is 48 bytes, the effect union starts at offset 16,
struct input_event is 24 bytes.
"""

from __future__ import annotations

import errno
import fcntl
import os
import struct
import time

EV_FF = 0x15
FF_CONSTANT = 0x52
FF_GAIN = 0x60
EVIOCSFF = 0x40304580      # _IOW('E', 0x80, struct ff_effect)
EVIOCRMFF = 0x40044581     # _IOW('E', 0x81, int)
EFFECT_SIZE = 48
LEFT, RIGHT = 0x4000, 0xC000

# Bits of /sys/class/input/eventN/device/capabilities/ff
EFFECT_NAMES = {0x50: "rumble", 0x51: "periodic", 0x52: "constant", 0x53: "spring", 0x54: "friction",
                0x55: "damper", 0x56: "inertia", 0x57: "ramp", 0x58: "square", 0x59: "triangle",
                0x5a: "sine", 0x5b: "saw up", 0x5c: "saw down", 0x5d: "custom", 0x60: "gain",
                0x61: "autocentre"}
# What a sim's force feedback mostly relies on.
CORE_EFFECTS = ("constant",)
USEFUL_EFFECTS = ("spring", "damper", "friction", "periodic")


def parse_caps(hexwords: str) -> list[str]:
    """capabilities/ff is space-separated hex words, most significant first."""
    words = (hexwords or "0").split()
    bits = 0
    for w in words:
        bits = (bits << 64) | int(w, 16)
    return [name for bit, name in sorted(EFFECT_NAMES.items()) if bits >> bit & 1]


def caps_summary(effects: list[str]) -> dict:
    missing = [e for e in CORE_EFFECTS + USEFUL_EFFECTS if e not in effects]
    if not effects:
        verdict = "none"
    elif any(e in missing for e in CORE_EFFECTS):
        verdict = "no_constant"
    elif missing:
        verdict = "partial"
    else:
        verdict = "full"
    return {"effects": effects, "missing": missing, "verdict": verdict}


def pack_constant(level: int, direction: int, length_ms: int, attack_ms: int = 150, fade_ms: int = 150,
                  effect_id: int = -1) -> bytearray:
    buf = bytearray(EFFECT_SIZE)
    struct.pack_into("<HhHHHHH", buf, 0, FF_CONSTANT, effect_id, direction, 0, 0, length_ms, 0)
    level = max(-0x7FFF, min(0x7FFF, int(level)))
    struct.pack_into("<hHHHH", buf, 16, level, attack_ms, 0, fade_ms, 0)
    return buf


def input_event(type_: int, code: int, value: int) -> bytes:
    return struct.pack("<qqHHi", 0, 0, type_, code, value)


def run_test(event_path: str, strength: float = 0.2, hold_s: float = 0.6, ioctl=None, sleep=time.sleep) -> dict:
    """Pull left, then right. strength is a fraction of the base's maximum and is
    capped at 40%, with a soft ramp, so it's safe on strong direct drive bases."""
    ioctl = ioctl or fcntl.ioctl
    strength = max(0.05, min(0.4, float(strength)))
    level = int(0x7FFF * strength)
    length = int(hold_s * 1000)
    try:
        fd = os.open(event_path, os.O_RDWR)
    except OSError as e:
        return {"ok": False, "message": f"Couldn't open {event_path}: {e.strerror}"}
    played = 0
    try:
        try:
            os.write(fd, input_event(EV_FF, FF_GAIN, 0xFFFF))   # full gain; games set their own
        except OSError:
            pass
        for direction in (LEFT, RIGHT):
            buf = pack_constant(level, direction, length)
            try:
                ioctl(fd, EVIOCSFF, buf, True)
            except OSError as e:
                if e.errno in (errno.EINVAL, errno.ENOSYS, errno.ENOTTY):
                    return {"ok": False, "message": "The driver doesn't accept a constant force effect, which most sims need."}
                return {"ok": False, "message": f"Uploading the test effect failed: {e.strerror}"}
            eid = struct.unpack_from("<h", buf, 2)[0]
            if eid < 0:
                return {"ok": False, "message": "The driver didn't accept the test effect."}
            try:
                os.write(fd, input_event(EV_FF, eid, 1))
                sleep(hold_s + 0.15)
                os.write(fd, input_event(EV_FF, eid, 0))
                played += 1
            finally:
                try:
                    ioctl(fd, EVIOCRMFF, eid)
                except OSError:
                    pass
            sleep(0.2)
    finally:
        os.close(fd)
    return {"ok": played == 2,
            "message": "Sent a pull to the left, then to the right. If the wheel moved, force feedback works "
                       "at the system level; if a game still has none, check its FFB settings, Steam Input "
                       "and the game's fixes in Pitwall."}
