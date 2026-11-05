"""
Performance analysis from MangoHud frametime logs.

Benchmark flow: Pitwall sets the game's launch options to run MangoHud with
logging, you drive for a minute or two, and Pitwall reads the newest log and
judges it against your target frame rate. For sim racing the 1% low and the
number of stutters matter more than average FPS.
"""

from __future__ import annotations

import csv
import glob
import os
import statistics


def benchmark_launch_options(log_dir: str, seconds: int = 90) -> str:
    cfg = f"autostart_log=1,log_duration={seconds},output_folder={log_dir}"
    return f"MANGOHUD=1 MANGOHUD_CONFIG={cfg} %command%"


def latest_log(log_dir: str) -> str | None:
    logs = [p for p in glob.glob(os.path.join(log_dir, "*.csv")) if not p.endswith("_summary.csv")]
    return max(logs, key=os.path.getmtime) if logs else None


def read_frametimes(path: str) -> list[float]:
    """MangoHud CSV: a couple of system-info lines, then a header row starting
    with 'fps', then one row per frame. Returns frametimes in ms."""
    with open(path, newline="", errors="ignore") as f:
        rows = list(csv.reader(f))
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "fps":
            header = [h.strip().lower() for h in row]
            col = header.index("frametime") if "frametime" in header else None
            out = []
            for r in rows[i + 1:]:
                try:
                    out.append(float(r[col]) if col is not None else 1000.0 / float(r[0]))
                except (ValueError, IndexError, ZeroDivisionError):
                    continue
            return [t for t in out if 0 < t < 1000]
    return []


def analyse(frametimes: list[float], target_fps: float = 60.0) -> dict:
    if len(frametimes) < 100:
        return {"ok": False, "message": "Not enough frames logged. Drive for at least a minute."}
    ft = sorted(frametimes)
    n = len(ft)
    avg = 1000.0 / statistics.fmean(frametimes)
    low1 = 1000.0 / ft[min(n - 1, int(n * 0.99))]
    low01 = 1000.0 / ft[min(n - 1, int(n * 0.999))]
    median = ft[n // 2]
    stutters = sum(1 for t in frametimes if t > max(2 * median, 1000.0 / target_fps * 1.5))
    minutes = sum(frametimes) / 60000.0
    per_min = stutters / minutes if minutes else 0
    budget = 1000.0 / target_fps

    if low1 >= target_fps * 0.97 and per_min < 2:
        verdict, advice = "great", [f"Holding {target_fps:.0f} FPS. You have headroom; try raising one setting at a time and re-test."]
    elif avg >= target_fps * 0.97 and (low1 < target_fps * 0.9 or per_min >= 2):
        verdict = "stutters"
        advice = ["Average FPS is fine but frame pacing isn't. Stutters usually come from shader compilation, "
                  "streaming or CPU spikes rather than raw GPU load.",
                  "Lower settings that hit the CPU: AI/opponent count, mirrors, reflections, physics detail.",
                  "Run the same track twice; first-run shader compilation stutters often disappear."]
    else:
        verdict = "too_slow"
        advice = [f"Averaging {avg:.0f} FPS against a {target_fps:.0f} target.",
                  "Lower resolution scale/upscaling first, then shadows and reflections.",
                  f"Or set a lower frame cap ({int(target_fps / 2)} FPS) in the Quick Access performance menu for steadier pacing."]
    return {"ok": True, "verdict": verdict, "avg_fps": round(avg, 1), "low1_fps": round(low1, 1),
            "low01_fps": round(low01, 1), "stutters_per_min": round(per_min, 1),
            "frames": n, "budget_ms": round(budget, 2), "advice": advice}


def analyse_latest(log_dir: str, target_fps: float = 60.0, game_hints: list | None = None) -> dict:
    path = latest_log(log_dir)
    if not path:
        return {"ok": False, "message": "No MangoHud log found yet. Start a benchmark, play, then check again."}
    res = analyse(read_frametimes(path), target_fps)
    res["log"] = os.path.basename(path)
    if res.get("ok") and game_hints and res["verdict"] != "great":
        res["advice"] = res["advice"] + game_hints
    return res
