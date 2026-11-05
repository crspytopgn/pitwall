"""SQLite lap storage."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib

from .laps import Lap

SCHEMA = """
CREATE TABLE IF NOT EXISTS laps (
    id INTEGER PRIMARY KEY,
    created REAL NOT NULL,
    sim TEXT NOT NULL,
    track_key TEXT NOT NULL,
    car TEXT,
    track TEXT,
    time REAL NOT NULL,
    length REAL,
    samples BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS laps_key ON laps(sim, track_key, car, time);
"""


def track_key(lap_or_sim, track=None, gate=None) -> str:
    """Laps are only comparable on the same layout. For sims without track
    names (BeamNG) the start-line position stands in for the track."""
    if track:
        return track
    if gate:
        return f"gate@{round(gate[0])},{round(gate[1])}"
    return "unknown"


class LapStore:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()

    def add(self, lap: Lap, key: str) -> int:
        blob = zlib.compress(json.dumps(lap.samples, separators=(",", ":")).encode())
        with self.lock, self.db:
            cur = self.db.execute(
                "INSERT INTO laps(created, sim, track_key, car, track, time, length, samples) VALUES (?,?,?,?,?,?,?,?)",
                (time.time(), lap.sim, key, lap.car, lap.track, lap.time, lap.length, blob))
            return cur.lastrowid

    def best(self, sim: str, key: str, car: str | None) -> tuple[int, Lap] | None:
        with self.lock:
            row = self.db.execute(
                "SELECT id, sim, car, track, time, length, samples FROM laps "
                "WHERE sim=? AND track_key=? AND (car IS ? OR car=?) ORDER BY time LIMIT 1",
                (sim, key, car, car)).fetchone()
        return (row[0], self._lap(row)) if row else None

    def get(self, lap_id: int) -> Lap | None:
        with self.lock:
            row = self.db.execute("SELECT id, sim, car, track, time, length, samples FROM laps WHERE id=?",
                                  (lap_id,)).fetchone()
        return self._lap(row) if row else None

    def recent(self, limit=20) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id, created, sim, track_key, car, track, time, length FROM laps ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(zip(("id", "created", "sim", "track_key", "car", "track", "time", "length"), r)) for r in rows]

    @staticmethod
    def _lap(row) -> Lap:
        _id, sim, car, track, t, length, blob = row
        return Lap(sim=sim, car=car, track=track, time=t, length=length,
                   samples=json.loads(zlib.decompress(blob)))
