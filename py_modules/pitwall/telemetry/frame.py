"""The one data shape every sim adapter produces."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict


@dataclass
class Frame:
    sim: str                       # "beamng", "lfs", "forza", "codemasters", "ac"
    t: float = 0.0                 # receive time (time.monotonic)
    active: bool = True            # False when the sim reports menu/pause/replay
    speed: float = 0.0             # m/s
    rpm: float = 0.0
    max_rpm: float | None = None
    gear: int = 0                  # -1 reverse, 0 neutral, 1.. forward
    throttle: float = 0.0          # 0..1
    brake: float = 0.0             # 0..1
    clutch: float = 0.0            # 0..1
    steer: float | None = None     # -1..1 (left negative) where known
    pos: tuple | None = None       # world position in metres as (horizontal x, horizontal y, height);
                                   # parsers reorder each sim's axes into this layout
    lap: int | None = None         # laps completed, if the sim counts laps
    lap_time: float | None = None  # current lap, seconds, if the sim reports it
    last_lap: float | None = None  # seconds
    best_lap: float | None = None  # seconds
    lap_dist: float | None = None  # metres into the lap, if the sim reports it
    lap_frac: float | None = None  # 0..1 around the lap, if the sim reports it
    fuel: float | None = None      # 0..1
    fuel_l: float | None = None    # litres in the tank, where the sim reports it
    fuel_cap_l: float | None = None  # tank capacity in litres
    tyre_temp: list | None = None  # [FL, FR, RL, RR] °C
    tyre_wear: list | None = None  # [FL, FR, RL, RR] raw wear value; direction varies by sim, so
                                   # strategy only uses how much it changes per lap
    tyre_window: tuple | None = None  # (cold, optimal, hot) °C where the sim reports it
    shift_light: bool = False
    car: str | None = None
    track: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def sanitize(self) -> "Frame":
        """Make a frame safe for everything downstream: non-finite numbers
        (NaN/inf from a sim's loading screen or a bad packet) become None or 0,
        and values are clamped to physical ranges. Without this a single NaN
        makes the dashboard's JSON invalid and freezes the phone."""
        def num(v, lo=None, hi=None, default=None):
            if v is None or isinstance(v, bool):
                return default if v is None else v
            try:
                v = float(v)
            except (TypeError, ValueError):
                return default
            if not math.isfinite(v):
                return default
            if lo is not None and v < lo:
                v = lo
            if hi is not None and v > hi:
                v = hi
            return v
        self.speed = num(self.speed, 0.0, 200.0, 0.0)          # m/s; 720 km/h covers everything
        self.rpm = num(self.rpm, 0.0, 40000.0, 0.0)
        self.max_rpm = num(self.max_rpm, 0.0, 40000.0) or None
        self.throttle = num(self.throttle, 0.0, 1.0, 0.0)
        self.brake = num(self.brake, 0.0, 1.0, 0.0)
        self.clutch = num(self.clutch, 0.0, 1.0, 0.0)
        self.steer = num(self.steer, -1.0, 1.0)
        try:
            self.gear = max(-1, min(15, int(self.gear)))
        except (TypeError, ValueError, OverflowError):
            self.gear = 0
        if self.lap is not None:
            try:
                self.lap = max(0, min(100000, int(self.lap)))
            except (TypeError, ValueError, OverflowError):
                self.lap = None
        for k in ("lap_time", "last_lap", "best_lap"):
            v = num(getattr(self, k), 0.0, 24 * 3600.0)
            setattr(self, k, v if v else (0.0 if k == "lap_time" and v == 0 else None))
        self.lap_dist = num(self.lap_dist, 0.0, 1e6)
        self.lap_frac = num(self.lap_frac, 0.0, 1.0)
        self.fuel = num(self.fuel, 0.0, 1.0)
        self.fuel_l = num(self.fuel_l, 0.0, 10000.0)
        self.fuel_cap_l = num(self.fuel_cap_l, 0.0, 10000.0) or None
        if self.pos is not None:
            try:
                p = tuple(float(x) for x in self.pos)
                self.pos = p if len(p) >= 2 and all(math.isfinite(x) and abs(x) < 1e7 for x in p) else None
            except (TypeError, ValueError):
                self.pos = None
        for k in ("tyre_temp", "tyre_wear"):
            v = getattr(self, k)
            if v is not None:
                try:
                    vals = [num(x, -100.0, 2000.0) for x in v]
                except TypeError:
                    vals = []
                setattr(self, k, vals if vals and any(x is not None for x in vals) else None)
        if self.tyre_window is not None:
            try:
                w = tuple(num(x, -100.0, 2000.0) for x in self.tyre_window)
                self.tyre_window = w if len(w) == 3 and None not in w else None
            except TypeError:
                self.tyre_window = None
        if self.extra:
            for k, v in list(self.extra.items()):
                if isinstance(v, float) and not math.isfinite(v):
                    self.extra[k] = None
                elif isinstance(v, (tuple, list)) and any(isinstance(x, float) and not math.isfinite(x) for x in v):
                    self.extra[k] = None
        return self
