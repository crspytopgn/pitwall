"""The one data shape every sim adapter produces."""

from __future__ import annotations

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
