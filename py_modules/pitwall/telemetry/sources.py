"""
Telemetry sources: one UDP listener for every UDP sim, and the Assetto Corsa
shared-memory parser (used by telemetry/shm.py).

Sources push Frames into a callback from daemon threads, so they never block
Decky's event loop.
"""

from __future__ import annotations

import selectors
import socket
import struct
import threading
import time

from .frame import Frame
from .parsers import F1Assembler, parse_codemasters, parse_forza, parse_motionsim, parse_outgauge

DEFAULT_PORTS = {
    "outgauge": 4444,      # BeamNG OutGauge (MotionSim may share it) and LFS
    "motionsim": 4445,     # BeamNG MotionSim, if sent to its own port
    "forza": 5300,
    "codemasters": 20777,  # Codemasters legacy UDP (DiRT Rally 1/2, DiRT 4, GRID Autosport)
    "f1": 20778,           # F1 2021/22/23; set the game's UDP port to 20778 (or share 20777, see below)
}


class UdpListener(threading.Thread):
    """One thread for every UDP port, using selectors: when no game is
    sending, it sleeps in a single select() call instead of waking per port.

    Packets are routed by port first, then by shape, so F1 packets arriving
    on the Codemasters port (both default to 20777 in-game) still work."""

    name_ = "udp"

    def __init__(self, ports: dict, on_frame, host: str = "0.0.0.0"):
        super().__init__(daemon=True, name="udp")
        self.ports, self.on_frame, self.host = dict(ports), on_frame, host
        self._stop = threading.Event()
        self.errors: dict[str, str] = {}
        self.packets: dict[str, int] = {k: 0 for k in self.ports}
        self.shared: dict = {}
        self.f1 = F1Assembler()
        self.error = None

    def stop(self):
        self._stop.set()

    def run(self):
        sel = selectors.DefaultSelector()
        socks = []
        for kind, port in self.ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, port))
                sock.setblocking(False)
                sel.register(sock, selectors.EVENT_READ, kind)
                socks.append(sock)
            except OSError as e:
                self.errors[kind] = f"Can't listen on UDP {port}: {e.strerror}"
        self.error = "; ".join(self.errors.values()) or None
        try:
            while not self._stop.is_set():
                for key, _ in sel.select(timeout=1.0):
                    kind = key.data
                    # drain everything queued on this socket
                    while True:
                        try:
                            data = key.fileobj.recv(2048)
                        except (BlockingIOError, InterruptedError):
                            break
                        except OSError:
                            break
                        self.packets[kind] = self.packets.get(kind, 0) + 1
                        self.handle(kind, data, time.monotonic())
        finally:
            for s in socks:
                sel.unregister(s)
                s.close()
            sel.close()

    def handle(self, kind: str, data: bytes, now: float):
        # A malformed packet must never stop the listener thread.
        try:
            self._dispatch(kind, data, now)
        except Exception as e:
            self.bad_packets = getattr(self, "bad_packets", 0) + 1
            if self.bad_packets in (1, 100, 10000):
                import logging
                logging.getLogger("pitwall").warning("Ignored bad %s packet (%d so far): %s", kind, self.bad_packets, e)

    def _dispatch(self, kind: str, data: bytes, now: float):
        frame = None
        if kind in ("outgauge", "motionsim"):
            motion = parse_motionsim(data)
            if motion:
                self.shared["motion"] = (now, motion)
                return
            frame = parse_outgauge(data)
            m = self.shared.get("motion")
            if frame and m and now - m[0] < 1.0:
                frame.pos = m[1]["pos"]
                frame.extra["acc"] = m[1]["acc"]
        elif kind == "forza":
            frame = parse_forza(data)
        elif kind in ("codemasters", "f1"):
            # F1 packets start with a format year; Codemasters legacy packets are 66 floats
            if len(data) != 264 and len(data) >= 2 and struct.unpack_from("<H", data, 0)[0] in (2021, 2022, 2023):
                frame = self.f1.feed(data)
            elif kind == "codemasters":
                frame = parse_codemasters(data)
        if frame:
            frame.t = now
            self.on_frame(frame)

    def status(self) -> list[dict]:
        return [{"name": f"udp:{k}", "port": p, "error": self.errors.get(k), "packets": self.packets.get(k, 0)}
                for k, p in self.ports.items()]


# ----------------------------------------------------------------- AC / ACC
# Struct offsets from the Assetto Corsa shared memory documentation
# (SPageFilePhysics / SPageFileGraphic / SPageFileStatic). Under Proton these
# only exist in /dev/shm when a bridge such as simshmbridge or winecarte runs
# alongside the game.


def _wstr(buf: bytes, off: int, chars: int) -> str:
    raw = buf[off:off + chars * 2]
    return raw.decode("utf-16-le", "ignore").split("\0", 1)[0]


def _ac_pos(graph: bytes):
    """Player car position (x, z, y with Y-up flipped). Assetto Corsa and EVO
    store one carCoordinates[3] at 252; ACC stores activeCars at 252, then
    carCoordinates[60][3], carID[60] and playerCarID, so find the player's slot."""
    import math
    if len(graph) >= 1220:
        active = struct.unpack_from("<i", graph, 252)[0]
        if 1 <= active <= 60:
            ids = struct.unpack_from("<60i", graph, 976)
            player = struct.unpack_from("<i", graph, 1216)[0]
            if player in ids[:active]:
                x, y, z = struct.unpack_from("<3f", graph, 256 + 12 * ids.index(player))
                if all(math.isfinite(v) and abs(v) < 1e5 for v in (x, y, z)):
                    return (x, z, y)
    if len(graph) >= 264:
        x, y, z = struct.unpack_from("<3f", graph, 252)
        if all(math.isfinite(v) and abs(v) < 1e5 for v in (x, y, z)) and (x or z):
            return (x, z, y)
    return None


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
        car=car, track=track, pos=_ac_pos(graph),
        fuel_l=fuel, fuel_cap_l=max_fuel, fuel=(fuel / max_fuel) if max_fuel else None,
        tyre_temp=core, tyre_wear=wear,
    )
