"""
Lap-vs-reference coaching. Finds braking zones on the reference (best) lap and
compares each one with the same zone on another lap: where braking started,
minimum speed, and time gained or lost through the zone.
"""

from __future__ import annotations

from .laps import interp_time

BRAKE_ON = 0.15
THROTTLE_BACK = 0.5
MATCH_WINDOW_M = 80.0
D, T, V, THR, BRK = 0, 1, 2, 3, 4


def braking_zones(samples: list) -> list[dict]:
    zones, i, n = [], 0, len(samples)
    while i < n:
        if samples[i][BRK] >= BRAKE_ON and (i == 0 or samples[i - 1][BRK] < BRAKE_ON):
            start = i
            j = i
            while j < n - 1 and not (samples[j][BRK] < BRAKE_ON and samples[j][THR] >= THROTTLE_BACK):
                j += 1
            seg = samples[start:j + 1]
            vmin_s = min(seg, key=lambda s: s[V])
            zones.append({
                "brake_at": samples[start][D],
                "end": samples[j][D],
                "entry_speed": samples[max(0, start - 1)][V],
                "min_speed": vmin_s[V],
                "apex": vmin_s[D],
            })
            i = j + 1
        else:
            i += 1
    # Merge stabs of brake closer than 30 m (trail-braking wobble).
    merged = []
    for z in zones:
        if merged and z["brake_at"] - merged[-1]["end"] < 30:
            m = merged[-1]
            m["end"] = z["end"]
            if z["min_speed"] < m["min_speed"]:
                m["min_speed"], m["apex"] = z["min_speed"], z["apex"]
        else:
            merged.append(z)
    return [z for z in merged if z["entry_speed"] - z["min_speed"] > 3]   # >~10 km/h scrubbed


def _zone_time(samples, a, b):
    ta, tb = interp_time(samples, a), interp_time(samples, b)
    return None if ta is None or tb is None else tb - ta


def compare(lap: list, ref: list, units: str = "kmh") -> dict:
    """Compare lap samples against reference samples."""
    conv = 3.6 if units == "kmh" else 2.23694
    unit = "km/h" if units == "kmh" else "mph"
    ref_z = braking_zones(ref)
    lap_z = braking_zones(lap)
    results = []
    for n, rz in enumerate(ref_z, 1):
        cands = [z for z in lap_z if abs(z["brake_at"] - rz["brake_at"]) < MATCH_WINDOW_M]
        if not cands:
            continue
        lz = min(cands, key=lambda z: abs(z["brake_at"] - rz["brake_at"]))
        a = rz["brake_at"] - 50
        b = rz["end"] + 50
        tl, tr = _zone_time(lap, a, b), _zone_time(ref, a, b)
        if tl is None or tr is None:
            continue
        loss = tl - tr
        early = rz["brake_at"] - lz["brake_at"]           # +ve = braked earlier than ref
        dv = (lz["min_speed"] - rz["min_speed"]) * conv  # -ve = slower at apex
        tip = None
        if loss > 0.05:
            parts = []
            if early > 8:
                parts.append(f"braked {early:.0f} m earlier")
            elif early < -8:
                parts.append(f"braked {-early:.0f} m later")
            if dv < -3:
                parts.append(f"{-dv:.0f} {unit} slower at the apex")
            elif dv > 3:
                parts.append(f"{dv:.0f} {unit} faster at the apex (likely overshot the exit)")
            if not parts:
                parts.append("slower on exit; get back to throttle sooner")
            tip = f"Corner {n} ({rz['brake_at']:.0f} m): lost {loss:.2f}s; " + ", ".join(parts) + "."
        results.append({"corner": n, "at": round(rz["brake_at"]), "loss": round(loss, 3),
                        "brake_diff_m": round(early, 1), "apex_speed_diff": round(dv, 1), "tip": tip})
    total = None
    if lap and ref:
        end = min(lap[-1][D], ref[-1][D])
        tl, tr = interp_time(lap, end), interp_time(ref, end)
        if tl is not None and tr is not None:
            total = round(tl - tr, 3)
    tips = [r["tip"] for r in sorted(results, key=lambda r: -r["loss"]) if r["tip"]][:3]
    return {"corners": results, "total_delta": total, "tips": tips}
