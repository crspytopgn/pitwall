"""
Shared-memory telemetry: sims that run under Proton and publish Windows named
memory (Assetto Corsa family, Automobilista 2 / Project CARS 2, rFactor 2,
Le Mans Ultimate, RaceRoom), plus Euro Truck Simulator 2 / American Truck
Simulator through the native Linux scs-sdk-plugin.

Under Proton these maps only exist inside the Wine prefix. A bridge running in
the same prefix (simshmbridge, winecarte, linux-simracing-utils) copies them to
/dev/shm, where Pitwall reads them.

Field offsets were generated with offsetof() from the C headers in Spacefreak18's
simapi (https://github.com/Spacefreak18/simapi, LGPL-3.0), which follow each
game's published SDK layout (all #pragma pack(4)). See tools/shm_offsets.c.
"""

from __future__ import annotations

import math
import mmap
import logging
import os
import struct
import threading
import time

from .frame import Frame
from .sources import parse_ac

SHM_DIR = "/dev/shm"


def _cstr(buf: bytes, off: int, n: int) -> str:
    return buf[off:off + n].split(b"\0", 1)[0].decode("utf-8", "replace").strip() or ""


def _f(buf, off):
    return struct.unpack_from("<f", buf, off)[0]


def _d(buf, off):
    return struct.unpack_from("<d", buf, off)[0]


def _i(buf, off):
    return struct.unpack_from("<i", buf, off)[0]


def _I(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def _yup(p):
    """Y-up world coordinates -> (x, z, y): horizontal plane first, height last."""
    return (p[0], p[2], p[1])


def _pos(v):
    return v if v and v > 0 else None


# ------------------------------------------------- AMS2 / Project CARS 2
PC2 = dict(game_state=8, viewed=20, participants=28, p_size=100, p_active=0, p_pos=68, p_lapdist=80,
           p_laps=88, thr=6428, brk=6432, steer=6436, clutch=6440, car=6444, track=6576, variation=6640,
           track_len=6704, invalid=6712, best=6716, last=6720, cur=6724, fuel=6840, speed=6848, rpm=6852,
           max_rpm=6856, gear=6876, tyre_temp=7072, tyre_wear=7136, fuel_cap=6844, seq=7320, size=7324)
PC2_PLAYING = 2


def parse_pcars2(buf: bytes) -> Frame | None:
    o = PC2
    if len(buf) < o["size"]:
        return None
    if _I(buf, o["seq"]) & 1:          # writer is mid-update
        return None
    state = _I(buf, o["game_state"])
    idx = _i(buf, o["viewed"])
    pos = lap_dist = laps = None
    if 0 <= idx < 64:
        p = o["participants"] + idx * o["p_size"]
        pos = struct.unpack_from("<3f", buf, p + o["p_pos"])
        lap_dist = _f(buf, p + o["p_lapdist"])
        laps = _I(buf, p + o["p_laps"])
    track_len = _f(buf, o["track_len"])
    track = _cstr(buf, o["track"], 64)
    var = _cstr(buf, o["variation"], 64)
    return Frame(
        sim="ams2", active=(state == PC2_PLAYING),
        speed=_f(buf, o["speed"]), rpm=_f(buf, o["rpm"]), max_rpm=_pos(_f(buf, o["max_rpm"])),
        gear=_i(buf, o["gear"]), throttle=_f(buf, o["thr"]), brake=_f(buf, o["brk"]),
        clutch=_f(buf, o["clutch"]), steer=_f(buf, o["steer"]),
        pos=(pos[0], pos[2], pos[1]) if pos else None, lap=laps,   # Y-up -> (x, z, y)
        lap_time=_pos(_f(buf, o["cur"])), last_lap=_pos(_f(buf, o["last"])), best_lap=_pos(_f(buf, o["best"])),
        lap_dist=lap_dist if lap_dist is not None and lap_dist >= 0 else None,
        lap_frac=(lap_dist / track_len) if (lap_dist and track_len > 0) else None,
        fuel=_f(buf, o["fuel"]), tyre_temp=[round(t, 1) for t in struct.unpack_from("<4f", buf, o["tyre_temp"])],
        fuel_cap_l=_pos(_f(buf, o["fuel_cap"])),
        fuel_l=(_f(buf, o["fuel"]) * _f(buf, o["fuel_cap"])) if _f(buf, o["fuel_cap"]) > 0 else None,
        tyre_wear=list(struct.unpack_from("<4f", buf, o["tyre_wear"])),
        car=_cstr(buf, o["car"], 64) or None,
        track=(f"{track} {var}".strip() or None),
        extra={"lap_invalid": bool(buf[o["invalid"]]), "track_length": track_len or None},
    )


# ------------------------------------------- rFactor 2 / Le Mans Ultimate
# Telemetry vehicle (rF2VehicleTelemetry / LMUVehicleTelemetry share layout)
VT = dict(size=1888, id=0, elapsed=12, lap=20, lap_start=24, vehicle=32, track=96, pos=160, vel=184,
          gear=352, rpm=356, max_rpm=532, thr=388, brk=396, steer=404, clutch=412, fuel=524, fuel_cap=608,
          wheels=848, wheel_size=260, w_wear=152, w_carcass=204)
KELVIN = 273.15
# Scoring info / vehicle
SI = dict(track=0, lap_dist=88, num=104, phase=108, realtime=115)
VS = dict(size=584, id=0, vehicle=36, laps=100, lap_dist=104, best=144, last=168, is_player=196)


def _vehicle_frame(sim, t: bytes, toff: int, sinfo: bytes, soff_info: int, sveh: bytes | None, svoff: int | None,
                   realtime: bool) -> Frame:
    v = VT
    vel = struct.unpack_from("<3d", t, toff + v["vel"])
    elapsed, lap_start = _d(t, toff + v["elapsed"]), _d(t, toff + v["lap_start"])
    fuel, cap = _d(t, toff + v["fuel"]), _d(t, toff + v["fuel_cap"])
    track_len = _d(sinfo, soff_info + SI["lap_dist"])
    lap_dist = best = last = laps = None
    if sveh is not None and svoff is not None:
        lap_dist = _d(sveh, svoff + VS["lap_dist"])
        best, last = _d(sveh, svoff + VS["best"]), _d(sveh, svoff + VS["last"])
        laps = struct.unpack_from("<h", sveh, svoff + VS["laps"])[0]
    return Frame(
        sim=sim, active=realtime,
        speed=math.sqrt(sum(c * c for c in vel)),
        rpm=_d(t, toff + v["rpm"]), max_rpm=_pos(_d(t, toff + v["max_rpm"])),
        gear=_i(t, toff + v["gear"]),
        throttle=_d(t, toff + v["thr"]), brake=_d(t, toff + v["brk"]),
        clutch=_d(t, toff + v["clutch"]), steer=_d(t, toff + v["steer"]),
        pos=_yup(struct.unpack_from("<3d", t, toff + v["pos"])),
        lap=laps, lap_time=(elapsed - lap_start) if elapsed >= lap_start > 0 or (lap_start == 0 and elapsed > 0) else None,
        last_lap=_pos(last), best_lap=_pos(best),
        lap_dist=lap_dist if lap_dist is not None and lap_dist >= 0 else None,
        lap_frac=(lap_dist / track_len) if (lap_dist is not None and track_len > 0) else None,
        fuel=(fuel / cap) if cap > 0 else None, fuel_l=fuel if cap > 0 else None, fuel_cap_l=cap or None,
        tyre_wear=[_d(t, toff + v["wheels"] + i * v["wheel_size"] + v["w_wear"]) for i in range(4)],
        tyre_temp=[round(_d(t, toff + v["wheels"] + i * v["wheel_size"] + v["w_carcass"]) - KELVIN, 1)
                   if _d(t, toff + v["wheels"] + i * v["wheel_size"] + v["w_carcass"]) > 0 else None for i in range(4)],
        car=_cstr(t, toff + v["vehicle"], 64) or None,
        track=_cstr(t, toff + v["track"], 64) or _cstr(sinfo, soff_info + SI["track"], 64) or None,
        extra={"track_length": track_len or None},
    )


RF2_TEL_VEH = 16
RF2_SC_INFO = 12
RF2_SC_VEH = 560


def parse_rf2(tel: bytes, scoring: bytes) -> Frame | None:
    if len(tel) < RF2_TEL_VEH + VT["size"] or len(scoring) < RF2_SC_VEH + VS["size"]:
        return None
    if _i(tel, 0) != _i(tel, 4) or _i(scoring, 0) != _i(scoring, 4):
        return None                                   # mid-update
    n_sc = max(0, min(64, _i(scoring, RF2_SC_INFO + SI["num"])))
    player_id = None
    svoff = None
    for k in range(n_sc):
        off = RF2_SC_VEH + k * VS["size"]
        if scoring[off + VS["is_player"]]:
            player_id, svoff = _i(scoring, off + VS["id"]), off
            break
    if player_id is None:
        return None
    n_t = max(0, min(64, _i(tel, 12)))
    for k in range(n_t):
        toff = RF2_TEL_VEH + k * VT["size"]
        if _i(tel, toff + VT["id"]) == player_id:
            realtime = bool(scoring[RF2_SC_INFO + SI["realtime"]])
            return _vehicle_frame("rf2", tel, toff, scoring, RF2_SC_INFO, scoring, svoff, realtime)
    return None


LMU_SCORING = 1632
LMU_TELEMETRY = 128464


def parse_lmu(buf: bytes) -> Frame | None:
    if len(buf) < LMU_TELEMETRY + 4 + VT["size"]:
        return None
    t0 = LMU_TELEMETRY
    if not buf[t0 + 2]:                              # playerHasVehicle
        return None
    idx = buf[t0 + 1]
    if idx >= 104:
        return None
    toff = t0 + 4 + idx * VT["size"]
    if toff + VT["size"] > len(buf):
        return None
    pid = _i(buf, toff + VT["id"])
    sinfo = LMU_SCORING
    n = max(0, min(104, _i(buf, sinfo + SI["num"])))
    svoff = None
    for k in range(n):
        off = sinfo + 560 + k * VS["size"]
        if off + VS["size"] > len(buf):
            break
        if _i(buf, off + VS["id"]) == pid:
            svoff = off
            break
    realtime = bool(buf[sinfo + SI["realtime"]])
    return _vehicle_frame("lmu", buf, toff, buf, sinfo, buf if svoff else None, svoff, realtime)


# ---------------------------------------------------------------- RaceRoom
R3E = dict(paused=20, menus=24, replay=28, track=600, layout=664, layout_len=736, laps=1028, lap_dist=1040,
           lap_frac=1044, best=1068, prev=1084, cur=1100, speed=1392, rps=1396, max_rps=1400, gear=1408,
           pos=1416, fuel=1456, fuel_cap=1460, thr=1504, brk=1512, clutch=1520, steer=1524,
           tire_wear=1680, tire_temp=1744, tire_temp_size=24)   # tire_temp: current[L,C,R], optimal, cold, hot
RPS_TO_RPM = 60 / (2 * math.pi)


def parse_r3e(buf: bytes) -> Frame | None:
    o = R3E
    if len(buf) < o["tire_temp"] + 4 * o["tire_temp_size"]:
        return None
    active = not (_i(buf, o["paused"]) or _i(buf, o["menus"]) or _i(buf, o["replay"]))
    cap = _f(buf, o["fuel_cap"])
    frac = _f(buf, o["lap_frac"])
    track = _cstr(buf, o["track"], 64)
    layout = _cstr(buf, o["layout"], 64)
    return Frame(
        sim="r3e", active=active,
        speed=max(0.0, _f(buf, o["speed"])), rpm=max(0.0, _f(buf, o["rps"]) * RPS_TO_RPM),
        max_rpm=_pos(_f(buf, o["max_rps"]) * RPS_TO_RPM),
        gear=_i(buf, o["gear"]), throttle=max(0.0, _f(buf, o["thr"])), brake=max(0.0, _f(buf, o["brk"])),
        clutch=max(0.0, _f(buf, o["clutch"])), steer=_f(buf, o["steer"]),
        pos=_yup(struct.unpack_from("<3f", buf, o["pos"])),
        lap=max(0, _i(buf, o["laps"])), lap_time=_pos(_f(buf, o["cur"])),
        last_lap=_pos(_f(buf, o["prev"])), best_lap=_pos(_f(buf, o["best"])),
        lap_dist=_pos(_f(buf, o["lap_dist"])), lap_frac=frac if 0 <= frac <= 1 else None,
        fuel=(_f(buf, o["fuel"]) / cap) if cap > 0 else None,
        fuel_l=_f(buf, o["fuel"]) if cap > 0 else None, fuel_cap_l=_pos(cap),
        tyre_wear=[w if w >= 0 else None for w in struct.unpack_from("<4f", buf, o["tire_wear"])],
        tyre_temp=[round(_f(buf, o["tire_temp"] + i * o["tire_temp_size"] + 4), 1) for i in range(4)],  # centre
        tyre_window=_r3e_window(buf, o),
        track=(f"{track} {layout}".strip() or None),
        extra={"track_length": _pos(_f(buf, o["layout_len"]))},
    )


def _r3e_window(buf, o):
    base = o["tire_temp"]
    cold, opt, hot = _f(buf, base + 16), _f(buf, base + 12), _f(buf, base + 20)
    return (round(cold, 1), round(opt, 1), round(hot, 1)) if 0 < cold < opt < hot else None


# ------------------------------------------- Euro Truck Simulator 2 / ATS
# scs-sdk-plugin (RenCloud) shared memory, native Linux build: /dev/shm/SCS/SCSTelemetry
SCS = dict(active=0, paused=4, game=52, gear=508,   # gearDashboard: what the driver sees, negative = reverse
           fuel_cap=704, max_rpm=740, speed=948, rpm=952, steer=956,
           thr=960, brk=964, clutch=968, fuel=1000, x=2200, brand=2364, name=2492, size=2556)


def parse_scs(buf) -> Frame | None:
    o = SCS
    if len(buf) < o["size"] or not buf[o["active"]]:
        return None
    cap = _f(buf, o["fuel_cap"])
    fuel = _f(buf, o["fuel"])
    x, y, z = struct.unpack_from("<3d", buf, o["x"])
    game = _I(buf, o["game"])
    brand, name = _cstr(buf, o["brand"], 64), _cstr(buf, o["name"], 64)
    return Frame(
        sim="ets2" if game == 1 else "ats" if game == 2 else "scs", active=not buf[o["paused"]],
        speed=abs(_f(buf, o["speed"])), rpm=_f(buf, o["rpm"]), max_rpm=_pos(_f(buf, o["max_rpm"])),
        gear=_i(buf, o["gear"]),
        throttle=_f(buf, o["thr"]), brake=_f(buf, o["brk"]), clutch=_f(buf, o["clutch"]), steer=_f(buf, o["steer"]),
        pos=(x, z, y),                                      # SCS is Y-up
        fuel=(fuel / cap) if cap > 0 else None, fuel_l=fuel if cap > 0 else None, fuel_cap_l=_pos(cap),
        car=f"{brand} {name}".strip() or None,
    )


# --------------------------------------------------------------- the source
READERS = [
    # (name, [candidate file sets], parser taking the mapped buffers,
    #  (offset, length) of a small region that changes whenever the sim writes)
    ("ac", [("acpmf_physics", "acpmf_graphics", "acpmf_static")],
     lambda b: parse_ac(b[0], b[1], b[2] if len(b) > 2 else None), (0, 4)),
    ("ams2", [("$pcars2$",), ("$pcars2",)], lambda b: parse_pcars2(b[0]), (PC2["seq"], 4)),
    ("lmu", [("LMU_Data",)], lambda b: parse_lmu(b[0]), (0, 64)),
    ("rf2", [("$rFactor2SMMP_Telemetry$", "$rFactor2SMMP_Scoring$")], lambda b: parse_rf2(b[0], b[1]), (0, 8)),
    ("r3e", [("$R3E",)], lambda b: parse_r3e(b[0]), (R3E["cur"], 4)),
    ("scs", [("SCS/SCSTelemetry",)], lambda b: parse_scs(b[0]), (8, 8)),   # 'time' stamp changes every update
]


class ShmSource(threading.Thread):
    """Polls /dev/shm for any known map and emits frames from whichever sim
    is live. Cheap when idle: one directory check every 2 s."""

    name_ = "shm"

    def __init__(self, on_frame, rate_hz: float = 60.0, shm_dir: str = SHM_DIR):
        super().__init__(daemon=True, name="shm")
        self.on_frame = on_frame
        self.period = 1.0 / rate_hz
        self.dir = shm_dir
        self._stop = threading.Event()
        self.error: str | None = None
        self.packets = 0
        self.active: str | None = None
        self.present: list[str] = []
        self.frozen_after = 10.0          # seconds without changes before another sim may take over

    def stop(self):
        self._stop.set()

    def _open(self, names):
        maps = []
        try:
            for n in names:
                path = os.path.join(self.dir, n)
                with open(path, "rb") as f:
                    size = os.fstat(f.fileno()).st_size
                    if size == 0:
                        raise OSError("empty")
                    maps.append(mmap.mmap(f.fileno(), size, access=mmap.ACCESS_READ))
        except OSError:
            for m in maps:
                m.close()
            return None
        return maps

    def scan(self, skip: set | None = None):
        """Return (name, maps, parser, sig) for the first sim whose maps exist,
        skipping sims whose maps were recently found frozen (left behind by a
        game that has exited), so another live sim can take over."""
        found = []
        hit = None
        for name, candidates, parser, sig in READERS:
            for names in candidates:
                if all(os.path.exists(os.path.join(self.dir, n)) for n in names[:2] if n):
                    found.append(name)
                    if hit is None and name not in (skip or ()):
                        maps = self._open(names) if name != "ac" else (self._open(names) or self._open(names[:2]))
                        if maps:
                            hit = (name, maps, parser, sig)
                    break
        self.present = found
        return hit

    def run(self):
        cur = None
        last_sig = None
        idle_since = time.monotonic()
        frozen: dict[str, float] = {}      # sim -> when its maps were found frozen
        while not self._stop.is_set():
            if cur is None:
                now = time.monotonic()
                frozen = {k: t for k, t in frozen.items() if now - t < 30}
                cur = self.scan(skip=set(frozen))
                if cur is None and frozen:
                    cur = self.scan()          # nothing else live: keep watching the frozen one
                if cur is None:
                    self.active = None
                    self._stop.wait(2.0)
                    continue
                self.active = cur[0]
            name, maps, parser, (s_off, s_len) = cur
            # Parsers read straight from the mmaps (no full copies), so idle
            # cost is a few bytes per tick even for LMU's 300 KB map.
            try:
                sig = maps[0][s_off:s_off + s_len]
            except (ValueError, OSError):
                cur = None
                continue
            if sig != last_sig:
                last_sig = sig
                idle_since = time.monotonic()
                try:
                    frame = parser(maps)
                except Exception:          # a torn or garbage read: skip this tick
                    frame = None
                if frame:
                    frame.t = time.monotonic()
                    self.packets += 1
                    try:
                        self.on_frame(frame)
                    except Exception:
                        logging.getLogger("pitwall").exception("Frame handler failed")
            elif time.monotonic() - idle_since > self.frozen_after:
                # Data stopped changing: the game probably exited. Rescan so a
                # different sim's bridge can take over.
                for m in maps:
                    m.close()
                frozen[name] = time.monotonic()
                cur = None
                last_sig = None
                idle_since = time.monotonic()
                continue
            self._stop.wait(self.period)
