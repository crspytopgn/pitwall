"""
Telemetry sources: UDP listeners and the Assetto Corsa shared-memory reader.

All sources push Frames into a callback. They run in daemon threads so they
never block Decky's event loop.
"""

from __future__ import annotations

import socket
import struct
import threading
import time

from .frame import Frame
from .parsers import parse_codemasters, parse_forza, parse_motionsim, parse_outgauge

DEFAULT_PORTS = {
    "outgauge": 4444,      # BeamNG OutGauge (MotionSim may share it) and LFS
    "motionsim": 4445,     # BeamNG MotionSim, if sent to its own port
    "forza": 5300,
    "codemasters": 20777,
}


class UdpSource(threading.Thread):
    """Listens on one UDP port and routes packets to the right parser by shape."""

    def __init__(self, kind: str, port: int, on_frame, host: str = "0.0.0.0", shared: dict | None = None):
        super().__init__(daemon=True, name=f"udp-{kind}")
        self.kind, self.port, self.on_frame = kind, port, on_frame
        self.host = host
        self._stop = threading.Event()
        # MotionSim and OutGauge may arrive on different ports; both sockets
        # share this dict so position gets merged into OutGauge frames.
        self.shared = shared if shared is not None else {}
        self.error: str | None = None
        self.packets = 0

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.settimeout(0.5)
        except OSError as e:
            self.error = f"Can't listen on UDP {self.port}: {e.strerror}"
            return
        with sock:
            while not self._stop.is_set():
                try:
                    data, _ = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                except OSError:
                    continue
                self.packets += 1
                self.handle(data, time.monotonic())

    def handle(self, data: bytes, now: float):
        frame = None
        if self.kind in ("outgauge", "motionsim"):
            motion = parse_motionsim(data)
            if motion:
                self.shared["motion"] = (now, motion)
                return
            frame = parse_outgauge(data)
            m = self.shared.get("motion")
            if frame and m and now - m[0] < 1.0:
                frame.pos = m[1]["pos"]
                frame.extra["acc"] = m[1]["acc"]
        elif self.kind == "forza":
            frame = parse_forza(data)
        elif self.kind == "codemasters":
            frame = parse_codemasters(data)
        if frame:
            frame.t = now
            self.on_frame(frame)


# ----------------------------------------------------------------- AC / ACC
# Struct offsets from the Assetto Corsa shared memory documentation
# (SPageFilePhysics / SPageFileGraphic / SPageFileStatic). Under Proton these
# only exist in /dev/shm when a bridge such as simshmbridge or winecarte runs
# alongside the game.


def _wstr(buf: bytes, off: int, chars: int) -> str:
    raw = buf[off:off + chars * 2]
    return raw.decode("utf-16-le", "ignore").split("\0", 1)[0]


def parse_ac(phys: bytes, graph: bytes, static: bytes | None) -> Frame | None:
    if len(phys) < 32 or len(graph) < 252:   # offsets verified against simapi's acdata.h
        return None
    gas, brake, fuel = struct.unpack_from("<3f", phys, 4)
    gear, rpm = struct.unpack_from("<2i", phys, 16)
    steer, speed_kmh = struct.unpack_from("<2f", phys, 24)
    status = struct.unpack_from("<i", graph, 4)[0]          # 0 off, 1 replay, 2 live, 3 pause
    laps = struct.unpack_from("<i", graph, 132)[0]
    cur, last, best = struct.unpack_from("<3i", graph, 140)
    frac = struct.unpack_from("<f", graph, 248)[0]
    car = track = None
    max_rpm = max_fuel = None
    if static and len(static) >= 420:
        car = _wstr(static, 68, 33) or None
        track = _wstr(static, 134, 33) or None
        max_rpm = struct.unpack_from("<i", static, 412)[0] or None
        max_fuel = struct.unpack_from("<f", static, 416)[0] or None
    wear = list(struct.unpack_from("<4f", phys, 120)) if len(phys) >= 168 else None
    core = [round(t, 1) for t in struct.unpack_from("<4f", phys, 152)] if len(phys) >= 168 else None
    ms = lambda v: v / 1000 if 0 < v < 2_000_000_000 else None
    return Frame(
        sim="ac", active=(status == 2),
        speed=speed_kmh / 3.6, rpm=float(rpm), max_rpm=max_rpm,
        gear=gear - 1, throttle=gas, brake=brake, steer=steer,
        lap=laps, lap_time=ms(cur), last_lap=ms(last), best_lap=ms(best),
        lap_frac=frac if 0 <= frac <= 1 else None,
        car=car, track=track,
        fuel_l=fuel, fuel_cap_l=max_fuel, fuel=(fuel / max_fuel) if max_fuel else None,
        tyre_temp=core, tyre_wear=wear,
    )
