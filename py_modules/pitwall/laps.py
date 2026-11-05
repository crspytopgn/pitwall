"""
Lap detection and per-lap sampling.

Sims that count laps (Forza, Codemasters, AC/ACC, LFS) are trusted directly.
BeamNG has no lap concept in its telemetry, so the driver marks a start/finish
point with "Set start line" and a lap ends each time the car passes back
through it.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from .telemetry.frame import Frame

SAMPLE_EVERY_M = 5.0      # one sample per 5 m travelled
MIN_LAP_S = 15.0
GATE_RADIUS_M = 15.0
PAUSE_GAP_S = 1.0         # no data for this long = paused; the gap isn't counted


@dataclass
class Lap:
    sim: str
    car: str | None
    track: str | None
    time: float
    length: float
    samples: list            # [dist, t, speed, throttle, brake, gear, steer, x, y]
    number: int | None = None


@dataclass
class _Current:
    t: float = 0.0
    dist: float = 0.0
    samples: list = field(default_factory=list)
    next_sample: float = 0.0
    started: bool = False


class LapTracker:
    def __init__(self, on_lap):
        self.on_lap = on_lap
        self.cur = _Current()
        self.gate: tuple | None = None          # (x, y) for sims without laps
        self._outside_gate = False
        self._prev_gate_d: float | None = None
        self._last: Frame | None = None
        self._last_lap_no: int | None = None
        self.reference: Lap | None = None       # best lap for live delta

    # ------------------------------------------------------------------
    def set_gate(self, pos: tuple | None):
        self.gate = (pos[0], pos[1]) if pos else None
        self._outside_gate = False
        self.reset_lap(start=True)

    def reset_lap(self, start=False):
        self.cur = _Current(started=start)

    # ------------------------------------------------------------------
    def update(self, f: Frame):
        prev = self._last
        self._last = f
        if not f.active:
            return
        if prev is None or prev.sim != f.sim:
            self._last_lap_no = f.lap
            self.reset_lap(start=False)
            return
        dt = f.t - prev.t
        if dt <= 0:
            return
        if dt > PAUSE_GAP_S:
            dt = 0.0

        # --- sims that count laps ---------------------------------------
        if f.lap is not None:
            if self._last_lap_no is not None and f.lap == self._last_lap_no + 1:
                self._finish(f, official=f.last_lap)
                self.cur = _Current(started=True)
            elif self._last_lap_no is not None and f.lap != self._last_lap_no:
                self.reset_lap(start=True)          # restart / session change
            self._last_lap_no = f.lap
        # --- gate-based (BeamNG) ----------------------------------------
        elif self.gate and f.pos:
            d = math.hypot(f.pos[0] - self.gate[0], f.pos[1] - self.gate[1])
            prev_d, self._prev_gate_d = self._prev_gate_d, d
            if d > GATE_RADIUS_M * 2:
                self._outside_gate = True
            # Lap ends at the closest approach to the gate (distance starts
            # growing again), so the start point doesn't jitter by the radius.
            elif d < GATE_RADIUS_M and self._outside_gate and prev_d is not None and d > prev_d:
                self._outside_gate = False
                if self.cur.started and self.cur.t >= MIN_LAP_S:
                    self._finish(f, official=None)
                self.cur = _Current(started=True)

        if not self.cur.started:
            return
        self.cur.t += dt
        if f.lap_dist is not None:
            self.cur.dist = f.lap_dist
        else:
            self.cur.dist += f.speed * dt
        if self.cur.dist >= self.cur.next_sample:
            x, y = (f.pos[0], f.pos[1]) if f.pos else (None, None)
            self.cur.samples.append([round(self.cur.dist, 1), round(self.cur.t, 3), round(f.speed, 2),
                                     round(f.throttle, 3), round(f.brake, 3), f.gear,
                                     None if f.steer is None else round(f.steer, 3), x, y])
            self.cur.next_sample = self.cur.dist + SAMPLE_EVERY_M

    def _finish(self, f: Frame, official: float | None):
        c = self.cur
        if not c.started or len(c.samples) < 20:
            return
        t = official if official and abs(official - c.t) < 5 else c.t
        if t < MIN_LAP_S:
            return
        lap = Lap(sim=f.sim, car=f.car, track=f.track, time=round(t, 3),
                  length=round(c.dist, 1), samples=c.samples, number=self._last_lap_no)
        self.on_lap(lap)

    # ------------------------------------------------------------------
    def live(self) -> dict:
        """Current lap time and delta to the reference lap at this distance."""
        c = self.cur
        out = {"lap_time": round(c.t, 2) if c.started else None,
               "lap_dist": round(c.dist, 1), "delta": None}
        ref = self.reference
        if c.started and ref and ref.samples:
            t_ref = interp_time(ref.samples, c.dist)
            if t_ref is not None:
                out["delta"] = round(c.t - t_ref, 2)
        return out


def interp_time(samples: list, dist: float) -> float | None:
    dists = [s[0] for s in samples]
    i = bisect.bisect_left(dists, dist)
    if i == 0 or i >= len(samples):
        return None
    d0, t0 = samples[i - 1][0], samples[i - 1][1]
    d1, t1 = samples[i][0], samples[i][1]
    if d1 == d0:
        return t0
    return t0 + (t1 - t0) * (dist - d0) / (d1 - d0)
