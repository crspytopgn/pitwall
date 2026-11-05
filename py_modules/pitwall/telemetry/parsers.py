"""
Packet parsers for UDP-based sims. Each parser takes raw bytes and returns a
Frame (or a partial dict for MotionSim), or None if the packet isn't theirs.

Sources:
- OutGauge (BeamNG.drive, Live for Speed): https://documentation.beamng.com/modding/protocols
- BeamNG MotionSim: same page ("BNG1" header + 21 floats)
- Forza "Data Out" (FM7 dash, FH4/FH5, Forza Motorsport 2023): community-documented
  Sled/Dash layout used by Forza's own Data Out setting
- Codemasters legacy UDP "extradata=3" (DiRT Rally 2.0, DiRT 4, GRID, older F1)
"""

from __future__ import annotations

import struct

from .frame import Frame

# ---------------------------------------------------------------- OutGauge
OUTGAUGE = struct.Struct("<I4sHBB7f2I3f16s16s")   # 92 bytes, +4 with optional id
assert OUTGAUGE.size == 92

DL_SHIFT = 1
DL_HANDBRAKE = 4
DL_TC = 16
DL_ABS = 1024


def parse_outgauge(data: bytes) -> Frame | None:
    if len(data) not in (92, 96):
        return None
    (_time, car, flags, gear, _plid, speed, rpm, turbo, eng_temp, fuel, _oilp, oil_temp,
     dash, show, throttle, brake, clutch, _d1, _d2) = OUTGAUGE.unpack_from(data)
    car_s = car.rstrip(b"\0").decode("latin-1", "replace")
    sim = "beamng" if car_s == "beam" else "lfs"
    return Frame(
        sim=sim,
        speed=speed, rpm=rpm, gear=gear - 1,
        throttle=throttle, brake=brake, clutch=clutch,
        fuel=fuel if 0 <= fuel <= 1 else None,
        shift_light=bool(show & DL_SHIFT),
        car=None if sim == "beamng" else car_s,
        extra={"turbo_bar": turbo, "engine_temp": eng_temp, "oil_temp": oil_temp,
               "abs": bool(show & DL_ABS), "tc": bool(show & DL_TC),
               "handbrake": bool(show & DL_HANDBRAKE), "metric": bool(flags & 16384)},
    )


# --------------------------------------------------------------- MotionSim
MOTIONSIM = struct.Struct("<4s21f")
assert MOTIONSIM.size == 88


def parse_motionsim(data: bytes) -> dict | None:
    if len(data) != 88 or data[:4] != b"BNG1":
        return None
    v = MOTIONSIM.unpack(data)[1:]
    return {
        "pos": (v[0], v[1], v[2]),
        "vel": (v[3], v[4], v[5]),
        "acc": (v[6], v[7], v[8]),
        "angles": (v[12], v[13], v[14]),  # roll, pitch, yaw
    }


# ------------------------------------------------------------------- Forza
_SLED = struct.Struct("<iIfff3f3f3f3f4f4f4f4i4f4f4f4f4f5i")
assert _SLED.size == 232
_DASH = struct.Struct("<3f3f4f7fHBBBBBBbbb")
assert _DASH.size == 79


def parse_forza(data: bytes) -> Frame | None:
    n = len(data)
    if n == 311 or n == 331:      # FM7 dash / Forza Motorsport (2023)
        dash_at = 232
    elif n == 324:                # Forza Horizon 4/5 (12 extra bytes after sled)
        dash_at = 244
    else:
        return None
    s = _SLED.unpack_from(data, 0)
    is_race_on, _ts, max_rpm, _idle, rpm = s[0], s[1], s[2], s[3], s[4]
    d = _DASH.unpack_from(data, dash_at)
    (px, py, pz, speed, _power, _torque, tfl, tfr, trl, trr, _boost, fuel, dist,
     best, last, cur, _race_t, lap_no, _pos, accel, brake, clutch, _hb, gear, steer,
     _line, _ai) = d
    f_to_c = lambda f: (f - 32) * 5 / 9
    return Frame(
        sim="forza", active=bool(is_race_on),
        speed=speed, rpm=rpm, max_rpm=max_rpm or None,
        gear=-1 if gear == 0 else (0 if gear >= 11 else gear),
        throttle=accel / 255, brake=brake / 255, clutch=clutch / 255,
        steer=steer / 127, pos=(px, py, pz),
        lap=lap_no, lap_time=cur or None,
        last_lap=last or None, best_lap=best or None,
        fuel=fuel, tyre_temp=[round(f_to_c(t), 1) for t in (tfl, tfr, trl, trr)],
        car=str(s[-5]),  # CarOrdinal
        extra={"distance_traveled": dist,
               "track": str(struct.unpack_from("<i", data, 327)[0]) if n == 331 else None},
    )


# ------------------------------------------------------------- Codemasters
_CM = struct.Struct("<66f")


def parse_codemasters(data: bytes) -> Frame | None:
    if len(data) < 264:
        return None
    v = _CM.unpack_from(data)
    gear = v[33]
    gear_i = -1 if (gear >= 9.5 or gear < -0.5) else int(round(gear))
    lap_len = v[61] if v[61] > 0 else None
    return Frame(
        sim="codemasters",
        speed=v[7], rpm=v[37] * 10, max_rpm=(v[63] * 10) or None,  # DR2 reports rpm/10
        gear=gear_i, throttle=v[29], brake=v[31], clutch=v[32], steer=v[30],
        pos=(v[4], v[5], v[6]),
        lap=int(v[36]), lap_time=v[1], last_lap=v[62] or None,
        lap_dist=max(0.0, v[2]),
        lap_frac=(v[2] / lap_len) if lap_len else None,
        fuel=(v[45] / v[46]) if v[46] > 0 else None,
        extra={"track_length": lap_len},
    )
