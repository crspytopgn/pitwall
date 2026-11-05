"""
The hub ties sources, lap tracking, storage and coaching together and holds
the live state the dashboard and Decky UI read.
"""

from __future__ import annotations

import threading
import time

from .coach import compare
from .laps import Lap, LapTracker
from .store import LapStore, track_key
from .strategy import Strategy
from .telemetry.frame import Frame
from .telemetry.shm import ShmSource
from .telemetry.sources import UdpListener, DEFAULT_PORTS

STALE_S = 2.0

SIM_NAMES = {"beamng": "BeamNG.drive", "lfs": "Live for Speed", "forza": "Forza", "codemasters": "Codemasters",
             "f1": "F1", "ac": "Assetto Corsa", "ams2": "AMS2 / Project CARS 2", "rf2": "rFactor 2",
             "lmu": "Le Mans Ultimate", "r3e": "RaceRoom", "ets2": "Euro Truck Simulator 2",
             "ats": "American Truck Simulator", "scs": "SCS truck sim"}


class Hub:
    def __init__(self, db_path: str, ports: dict | None = None, logger=None, enable_shm=True):
        self.log = logger
        self.ports = {**DEFAULT_PORTS, **(ports or {})}
        self.store = LapStore(db_path)
        self.tracker = LapTracker(self._on_lap)
        self.lock = threading.Lock()
        self.frame: Frame | None = None
        self.last_lap: dict | None = None
        self.last_coaching: dict | None = None
        self.session_laps: list[dict] = []
        self.listeners: list = []
        self.car_listeners: list = []        # called with (sim, car) when the car changes
        self.strategy = Strategy()
        self._car_key = None
        self.sources = [UdpListener(self.ports, self._on_frame)] if self.ports else []
        if enable_shm:
            self.sources.append(ShmSource(self._on_frame))
        self._ref_key = None

    def start(self):
        for s in self.sources:
            s.start()

    def stop(self):
        for s in self.sources:
            s.stop()

    # ------------------------------------------------------------------
    def _key(self, f_or_lap) -> str:
        return track_key(f_or_lap.sim, f_or_lap.track, self.tracker.gate)

    def _on_frame(self, f: Frame):
        with self.lock:
            prev = self.frame
            self.frame = f
            self.tracker.update(f)
            key = (f.sim, self._key(f), f.car)
            if key != self._ref_key:
                self._ref_key = key
                best = self.store.best(*key)
                self.tracker.reference = best[1] if best else None
        self.strategy.on_frame(f)
        for cb in list(self.listeners):
            try:
                cb(f)
            except Exception:
                pass
        car_key = (f.sim, f.car) if f.car and f.active else None
        if car_key and car_key != self._car_key:
            self._car_key = car_key
            for cb in list(self.car_listeners):
                try:
                    cb(f.sim, f.car)
                except Exception:
                    pass
        if prev is None or prev.sim != f.sim:
            self._info(f"Telemetry from {f.sim}")

    def _on_lap(self, lap: Lap):
        self.strategy.on_lap(lap.time)
        key = self._key(lap)
        ref = self.tracker.reference
        lap_id = self.store.add(lap, key)
        coaching = compare(lap.samples, ref.samples) if ref else None
        is_best = ref is None or lap.time < ref.time
        if is_best:
            self.tracker.reference = lap
        summary = {"id": lap_id, "time": lap.time, "best": is_best,
                   "ref_time": ref.time if ref else None, "sim": lap.sim,
                   "car": lap.car, "track": lap.track or key, "at": time.time()}
        self.last_lap = summary
        self.last_coaching = coaching
        self.session_laps.append({**summary, "coaching": coaching})
        self._info(f"Lap {lap.time:.3f}s{' (best)' if is_best else ''}")

    def _info(self, msg):
        if self.log:
            self.log.info(msg)

    # ------------------------------------------------------------------
    def reset_car(self):
        with self.lock:
            self._car_key = None

    def set_start_line(self) -> bool:
        with self.lock:
            f = self.frame
            if not f or not f.pos:
                return False
            self.tracker.set_gate(f.pos)
            self._ref_key = None
            return True

    def status(self) -> dict:
        with self.lock:
            f = self.frame
            live = self.tracker.live()
            fresh = bool(f and time.monotonic() - f.t < STALE_S)
            return {
                "receiving": fresh,
                "sim": f.sim if f else None,
                "sim_name": SIM_NAMES.get(f.sim, f.sim) if f else None,
                "car": f.car if f else None,
                "track": f.track if f else None,
                "needs_start_line": bool(fresh and f.lap is None and self.tracker.gate is None),
                "has_position": bool(f and f.pos),
                "live": live,
                "best": self.tracker.reference.time if self.tracker.reference else None,
                "last_lap": self.last_lap,
                "tips": (self.last_coaching or {}).get("tips", []),
                "session_laps": len(self.session_laps),
                "sources": self._sources_status(),
            }

    def _sources_status(self) -> list[dict]:
        out = []
        for s in self.sources:
            if hasattr(s, "status"):
                out += s.status()
            else:
                out.append({"name": s.name, "error": s.error, "packets": s.packets,
                            "active": getattr(s, "active", None), "present": getattr(s, "present", None)})
        return out

    def snapshot(self) -> dict:
        """Compact live payload for the dashboard (sent ~15x a second)."""
        with self.lock:
            f = self.frame
            if not f:
                return {"receiving": False}
            live = self.tracker.live()
            ref = self.tracker.reference
            return {
                "receiving": time.monotonic() - f.t < STALE_S,
                "sim": f.sim, "sim_name": SIM_NAMES.get(f.sim, f.sim), "speed": f.speed, "rpm": f.rpm, "max_rpm": f.max_rpm,
                "gear": f.gear, "throttle": f.throttle, "brake": f.brake, "clutch": f.clutch,
                "steer": f.steer, "tyre_temp": f.tyre_temp,
                "fuel": f.fuel if f.fuel is not None else ((f.fuel_l / f.fuel_cap_l) if (f.fuel_l is not None and f.fuel_cap_l) else None),
                "shift": f.shift_light, "abs": f.extra.get("abs"), "tc": f.extra.get("tc"),
                "lap_time": live["lap_time"] if live["lap_time"] is not None else f.lap_time,
                "delta": live["delta"], "best": ref.time if ref else f.best_lap,
                "last": self.last_lap["time"] if self.last_lap else f.last_lap,
                "tips": (self.last_coaching or {}).get("tips", []),
                "coached": self.last_coaching is not None,
                "needs_start_line": f.lap is None and self.tracker.gate is None,
                "pos": [round(f.pos[0], 1), round(f.pos[1], 1)] if f.pos else None,
                "lap_id": self.last_lap["id"] if self.last_lap else None,
                "lap_best": bool(self.last_lap and self.last_lap["best"]),
                "strategy": self._strategy_brief(),
            }

    def _strategy_brief(self):
        now = time.monotonic()
        cached = getattr(self, "_brief_cache", None)
        if cached and now - cached[0] < 0.5:
            return cached[1]
        brief = self._strategy_brief_uncached()
        self._brief_cache = (now, brief)
        return brief

    def _strategy_brief_uncached(self):
        r = self.strategy.report()
        fu, ty = r.get("fuel") or {}, r.get("tyres") or {}
        return {"fuel_now": fu.get("now"), "fuel_unit": fu.get("unit"), "laps_left": fu.get("laps_left"),
                "to_add": fu.get("to_add"), "temps": ty.get("temps"), "window": ty.get("window")}

    def track_map(self, max_points: int = 400) -> dict:
        """Outline of the reference lap (or the lap in progress) for the
        dashboard's track map."""
        with self.lock:
            ref = self.tracker.reference
            pts = [(s[7], s[8]) for s in (ref.samples if ref else self.tracker.cur.samples)
                   if s[7] is not None and s[8] is not None]
        if len(pts) > max_points:
            step = len(pts) / max_points
            pts = [pts[int(i * step)] for i in range(max_points)]
        return {"points": [[round(x, 1), round(y, 1)] for x, y in pts], "is_reference": bool(ref)}

    def session_summary(self) -> dict:
        with self.lock:
            return {"laps": list(self.session_laps)}
