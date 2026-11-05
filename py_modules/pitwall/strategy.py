"""
Fuel and tyre strategy from live telemetry.

Fuel: measured use per lap (median of recent clean laps), laps left in the
tank, and how much to add to reach the end of the race. Refuelling (fuel
going up) and partial first laps are ignored.

Tyres: live temperatures with front/rear and left/right balance, the sim's
own temperature window where it reports one (RaceRoom), and wear per lap.
Sims count wear in different directions, so Pitwall only uses how much the
value changes each lap.
"""

from __future__ import annotations

import math
import statistics
import threading

RECENT = 5
TYRES = ("FL", "FR", "RL", "RR")


class Strategy:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()
        self.target_laps: float | None = None     # laps left in the race, set by the driver
        self.target_minutes: float | None = None  # or minutes left

    def reset(self):
        self.sim = None
        self.fuel_at_lap_start = None
        self.wear_at_lap_start = None
        self.fuel_per_lap: list[float] = []
        self.wear_per_lap: list[list[float]] = []
        self.lap_times: list[float] = []
        self.latest = None
        self._lap_fuel_up = False
        self._baseline_from_lap_start = False   # first lap after joining is partial

    # ------------------------------------------------------------------
    def on_frame(self, f):
        with self.lock:
            if f.sim != self.sim:
                self.reset()
                self.sim = f.sim
            prev = self.latest
            self.latest = f
            fuel = self._fuel(f)
            if fuel is not None and prev is not None:
                pf = self._fuel(prev)
                if pf is not None and fuel > pf + 0.5 * (1 if f.fuel_l is not None else 0.01):
                    self._lap_fuel_up = True          # refuelled: this lap's figure is meaningless
            if self.fuel_at_lap_start is None:
                self.fuel_at_lap_start = fuel
            if self.wear_at_lap_start is None and f.tyre_wear:
                self.wear_at_lap_start = list(f.tyre_wear)

    def on_lap(self, lap_time: float):
        with self.lock:
            f = self.latest
            if f is None:
                return
            fuel = self._fuel(f)
            usable = self._baseline_from_lap_start
            self._baseline_from_lap_start = True
            if (usable and fuel is not None and self.fuel_at_lap_start is not None and not self._lap_fuel_up):
                used = self.fuel_at_lap_start - fuel
                if used > 0:
                    self.fuel_per_lap.append(used)
            if usable and f.tyre_wear and self.wear_at_lap_start and len(f.tyre_wear) == 4:
                d = [abs((a or 0) - (b or 0)) for a, b in zip(f.tyre_wear, self.wear_at_lap_start)]
                if any(x > 0 for x in d) and max(d) < 0.5:   # ignore tyre changes
                    self.wear_per_lap.append(d)
            if lap_time and lap_time > 0:
                self.lap_times.append(lap_time)
            self.fuel_at_lap_start = fuel
            self.wear_at_lap_start = list(f.tyre_wear) if f.tyre_wear else None
            self._lap_fuel_up = False

    def set_target(self, laps: float | None = None, minutes: float | None = None):
        with self.lock:
            self.target_laps = laps if laps and laps > 0 else None
            self.target_minutes = minutes if minutes and minutes > 0 else None

    @staticmethod
    def _fuel(f):
        if f.fuel_l is not None:
            return f.fuel_l
        return f.fuel   # fraction 0..1

    # ------------------------------------------------------------------
    def report(self) -> dict:
        with self.lock:
            f = self.latest
            out = {"sim": self.sim, "fuel": None, "tyres": None,
                   "target_laps": self.target_laps, "target_minutes": self.target_minutes}
            if f is None:
                return out
            litres = f.fuel_l is not None
            unit = "L" if litres else "%"
            scale = 1 if litres else 100
            now = self._fuel(f)
            recent = self.fuel_per_lap[-RECENT:]
            per_lap = statistics.median(recent) if recent else None
            avg_lap = statistics.median(self.lap_times[-RECENT:]) if self.lap_times else None
            fuel = {"unit": unit, "now": round(now * scale, 2) if now is not None else None,
                    "per_lap": round(per_lap * scale, 3) if per_lap else None, "laps_measured": len(self.fuel_per_lap),
                    "laps_left": round(now / per_lap, 1) if (per_lap and now is not None) else None,
                    "capacity": f.fuel_cap_l if litres else 100}
            laps_needed = self.target_laps
            if laps_needed is None and self.target_minutes and avg_lap:
                laps_needed = math.ceil(self.target_minutes * 60 / avg_lap)
            if laps_needed and per_lap and now is not None:
                need = (laps_needed + 1) * per_lap      # one lap of margin
                add = max(0.0, need - now)
                fuel["to_finish"] = round(need * scale, 1)
                fuel["to_add"] = round(add * scale, 1)
                if litres and f.fuel_cap_l and need > f.fuel_cap_l:
                    fuel["stops"] = math.ceil((need - now) / f.fuel_cap_l) if need > now else 0
                fuel["advice"] = (f"Add {add * scale:.1f} {unit} at your stop (includes a lap of margin)."
                                  if add > 0 else "Enough fuel to finish with a lap of margin.")
            out["fuel"] = fuel if (now is not None) else None

            if f.tyre_temp and any(t is not None for t in f.tyre_temp):
                temps = [t if t is not None else None for t in f.tyre_temp]
                tyres = {"temps": dict(zip(TYRES, temps)), "window": f.tyre_window}
                valid = [t for t in temps if t is not None]
                if len(valid) == 4:
                    front, rear = (temps[0] + temps[1]) / 2, (temps[2] + temps[3]) / 2
                    left, right = (temps[0] + temps[2]) / 2, (temps[1] + temps[3]) / 2
                    tyres["front_rear"] = round(front - rear, 1)
                    tyres["left_right"] = round(left - right, 1)
                    notes = []
                    if abs(front - rear) > 8:
                        notes.append(("Fronts" if front > rear else "Rears") + f" running {abs(front - rear):.0f}°C hotter: "
                                     + ("likely understeer or heavy braking." if front > rear else "likely wheelspin or oversteer."))
                    if f.tyre_window:
                        cold, _opt, hot = f.tyre_window
                        for name, t in zip(TYRES, temps):
                            if t < cold:
                                notes.append(f"{name} below its window ({t:.0f}°C < {cold:.0f}°C).")
                            elif t > hot:
                                notes.append(f"{name} above its window ({t:.0f}°C > {hot:.0f}°C).")
                    tyres["notes"] = notes
                out["tyres"] = tyres
            if self.wear_per_lap:
                recent_w = self.wear_per_lap[-RECENT:]
                per = [statistics.median(c) for c in zip(*recent_w)]
                worst = max(range(4), key=lambda i: per[i])
                tyres = out["tyres"] or {"temps": None}
                tyres["wear_per_lap_pct"] = dict(zip(TYRES, [round(p * 100, 2) for p in per]))
                tyres["worst"] = TYRES[worst]
                if per[worst] > 0:
                    tyres["laps_per_10pct"] = round(0.10 / per[worst], 1)
                out["tyres"] = tyres
            return out
