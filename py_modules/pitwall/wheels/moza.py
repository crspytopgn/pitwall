"""
Minimal MOZA Racing serial protocol driver.

Protocol and command table are taken from Boxflat by Tomasz Pakula
(https://github.com/Lawstorant/boxflat, GPL-3.0), which reverse engineered it.
This module has no third-party dependencies (no pyserial) so it runs on the
Python bundled with Decky Loader.

Frame layout (all values big-endian):

    0x7e | n | group | device | command id bytes... | payload... | checksum

where n = len(command id) + len(payload) and
checksum = (0x0d + sum(all previous bytes)) % 256.

A response mirrors the request with group | 0x80 and the device id's nibbles
swapped (0x13 -> 0x31).
"""

from __future__ import annotations

import glob
import os
import re
import select
import termios
import threading
import time
from dataclasses import dataclass
from typing import Callable

MSG_START = 0x7E
MAGIC = 0x0D

DEV_MAIN = 18
DEV_BASE = 19


@dataclass(frozen=True)
class Setting:
    key: str          # name used by the UI and in profiles
    cmd_id: tuple     # command id bytes
    size: int         # payload size in bytes
    to_dev: Callable[[float], int]
    from_dev: Callable[[int], float]
    lo: float
    hi: float
    read_group: int = 40
    write_group: int = 41
    device: int = DEV_BASE
    mirror_ids: tuple = ()  # extra command ids written with the same value


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# UI value <-> device value conversions mirror Boxflat's base panel.
SETTINGS: dict[str, Setting] = {s.key: s for s in [
    # Rotation in degrees. Device stores half the lock-to-lock angle.
    # Boxflat writes both "limit" (id 1) and "max-angle" (id 23).
    Setting("rotation", (1,), 2, lambda v: round(v / 2), lambda d: d * 2, 90, 2700,
            mirror_ids=((23,),)),
    Setting("ffb_strength", (2,), 2, lambda v: round(v * 10), lambda d: round(d / 10), 0, 100),
    Setting("torque", (18,), 2, lambda v: round(v), lambda d: d, 50, 100),
    Setting("speed", (10,), 2, lambda v: round(v * 10), lambda d: round(d / 10), 0, 100),
    Setting("damper", (7,), 2, lambda v: round(v * 10), lambda d: round(d / 10), 0, 100),
    Setting("friction", (8,), 2, lambda v: round(v * 10), lambda d: round(d / 10), 0, 100),
    Setting("inertia", (4,), 2, lambda v: round(v * 10), lambda d: round(d / 10), 0, 100),
    Setting("spring", (9,), 2, lambda v: round(v * 10), lambda d: round(d / 10), 0, 100),
    # Boxflat: device = ui * 4 + 10
    Setting("road_sensitivity", (12,), 2, lambda v: round(v * 4 + 10),
            lambda d: _clamp(round((d - 10) / 4), 0, 10), 0, 10),
    # Device command is "ffb-disable": 1 = disabled. UI uses enabled = 1.
    Setting("ffb_enabled", (254,), 2, lambda v: 0 if v else 1, lambda d: 0 if d else 1, 0, 1),
]}

# FFB on/off is deliberately not stored in profiles, so a profile saved with
# FFB off can never silently disable it at game launch.
PROFILE_KEYS = [k for k in SETTINGS if k != "ffb_enabled"]

CALIBRATE = dict(group=42, cmd_id=(1,), size=2)

BASE_NAME_RE = re.compile(r"gudsen.*(r[0-9]{1,2}).*(base|racing_wheel)", re.I)


def checksum(data: bytes) -> int:
    return (MAGIC + sum(data)) % 256


def build_frame(group: int, device: int, cmd_id: tuple, payload: bytes) -> bytes:
    body = bytes([MSG_START, len(cmd_id) + len(payload), group, device, *cmd_id]) + payload
    return body + bytes([checksum(body)])


def swap_nibbles(b: int) -> int:
    return ((b & 0x0F) << 4) | ((b & 0xF0) >> 4)


def parse_frames(buf: bytearray) -> list[tuple[int, int, bytes]]:
    """Consume complete frames from buf. Returns (request_group, device, data)
    with the response bit cleared and the device id un-swapped."""
    out = []
    while True:
        start = buf.find(bytes([MSG_START]))
        if start < 0:
            buf.clear()
            return out
        if start:
            del buf[:start]
        if len(buf) < 2:
            return out
        n = buf[1]
        if not 1 <= n <= 64:
            del buf[:1]
            continue
        total = n + 5
        if len(buf) < total:
            return out
        frame = bytes(buf[:total])
        del buf[:total]
        group = frame[2] & 0x7F
        device = swap_nibbles(frame[3])
        out.append((group, device, frame[4:4 + n]))


def find_base() -> str | None:
    """Locate the wheelbase's serial node."""
    by_id = sorted(glob.glob("/dev/serial/by-id/*"))
    for p in by_id:
        if BASE_NAME_RE.search(os.path.basename(p)):
            return p
    # Fallback: any ttyACM whose USB vendor is 346e (Gudsen/MOZA).
    for tty in sorted(glob.glob("/sys/class/tty/ttyACM*")):
        dev = os.path.realpath(os.path.join(tty, "device"))
        for _ in range(4):
            vid = os.path.join(dev, "idVendor")
            if os.path.exists(vid):
                try:
                    with open(vid) as f:
                        if f.read().strip().lower() == "346e":
                            return "/dev/" + os.path.basename(tty)
                except OSError:
                    pass
                break
            dev = os.path.dirname(dev)
    return None


class MozaBase:
    def __init__(self, logger=None, path_override: str | None = None):
        self._fd: int | None = None
        self._path: str | None = None
        self._lock = threading.Lock()
        self._log = logger
        self._override = path_override
        self.last_error: str | None = None

    # ---- connection -------------------------------------------------------
    @property
    def path(self):
        return self._path

    def _info(self, msg):
        if self._log:
            self._log.info(msg)

    def close(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
        self._fd = None
        self._path = None

    def _ensure_open(self) -> bool:
        if self._fd is not None:
            if self._path and os.path.exists(self._path):
                return True
            self.close()
        path = self._override or find_base()
        if not path:
            self.last_error = "No MOZA wheelbase found"
            return False
        try:
            fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            attrs = termios.tcgetattr(fd)
            # raw mode: cfmakeraw equivalent
            attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK | termios.ISTRIP
                          | termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IXON)
            attrs[1] &= ~termios.OPOST
            attrs[2] &= ~(termios.CSIZE | termios.PARENB)
            attrs[2] |= termios.CS8 | termios.CREAD | termios.CLOCAL
            attrs[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON | termios.ISIG | termios.IEXTEN)
            attrs[4] = attrs[5] = termios.B115200
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            termios.tcflush(fd, termios.TCIOFLUSH)
        except OSError as e:
            self.last_error = f"Cannot open {path}: {e.strerror}"
            return False
        except termios.error:
            pass  # not a real tty (e.g. some test setups); carry on
        self._fd, self._path = fd, path
        self.last_error = None
        self._info(f"Opened wheelbase at {path}")
        return True

    def connected(self) -> bool:
        with self._lock:
            return self._ensure_open()

    # ---- I/O --------------------------------------------------------------
    def _transact(self, frames: list[bytes], expect: set, timeout=0.6):
        """Write frames, then collect responses until every key in expect
        (group, device, cmd_id) is seen or timeout. Returns {key: payload}."""
        if not self._ensure_open():
            return None
        fd = self._fd
        try:
            for f in frames:
                os.write(fd, f)
                time.sleep(0.003)  # gentle pacing, as Boxflat writes one at a time
            buf = bytearray()
            got: dict = {}
            deadline = time.monotonic() + timeout
            while expect - got.keys():
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                r, _, _ = select.select([fd], [], [], left)
                if not r:
                    break
                chunk = os.read(fd, 512)
                if not chunk:
                    break
                buf.extend(chunk)
                for group, device, data in parse_frames(buf):
                    for key in expect:
                        g, d, cid = key
                        if g == group and d == device and tuple(data[:len(cid)]) == cid:
                            got[key] = data[len(cid):]
            return got
        except OSError as e:
            self.last_error = f"Serial error: {e.strerror}"
            self.close()
            return None

    def read_all(self) -> dict | None:
        with self._lock:
            frames, expect, keymap = [], set(), {}
            for s in SETTINGS.values():
                frames.append(build_frame(s.read_group, s.device, s.cmd_id, (1).to_bytes(s.size, "big")))
                k = (s.read_group, s.device, s.cmd_id)
                expect.add(k)
                keymap[k] = s
            got = self._transact(frames, expect)
            if got is None:
                return None
            out = {}
            for k, payload in got.items():
                s = keymap[k]
                if len(payload) >= s.size:
                    out[s.key] = s.from_dev(int.from_bytes(payload[:s.size], "big"))
            return out

    def write(self, values: dict) -> bool:
        frames, expect = [], set()
        for key, v in values.items():
            s = SETTINGS.get(key)
            if s is None or v is None:
                continue
            dev = int(s.to_dev(_clamp(float(v), s.lo, s.hi)))
            dev = _clamp(dev, 0, (1 << (8 * s.size)) - 1)
            payload = dev.to_bytes(s.size, "big")
            for cid in (s.cmd_id, *s.mirror_ids):
                frames.append(build_frame(s.write_group, s.device, cid, payload))
                expect.add((s.write_group, s.device, cid))
        if not frames:
            return True
        with self._lock:
            got = self._transact(frames, expect, timeout=0.4)
        return got is not None

    def calibrate_center(self) -> bool:
        c = CALIBRATE
        with self._lock:
            got = self._transact([build_frame(c["group"], DEV_BASE, c["cmd_id"], (1).to_bytes(c["size"], "big"))],
                                 {(c["group"], DEV_BASE, c["cmd_id"])}, timeout=0.4)
        return got is not None
