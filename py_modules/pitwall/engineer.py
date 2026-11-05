"""
Race engineer debrief. Always produces an offline summary from Pitwall's own
analysis; if the user has added an Anthropic API key, it also asks Claude for
a short spoken-style debrief based on that summary.
"""

from __future__ import annotations

import json
import urllib.request

API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-5-5"


def build_summary(session: dict) -> dict:
    laps = session.get("laps", [])
    if not laps:
        return {"laps": 0}
    times = [l["time"] for l in laps]
    best = min(times)
    worst_corners: dict[int, list] = {}
    for l in laps:
        for c in ((l.get("coaching") or {}).get("corners") or []):
            worst_corners.setdefault(c["corner"], []).append(c)
    corner_avgs = []
    for n, cs in worst_corners.items():
        avg_loss = sum(c["loss"] for c in cs) / len(cs)
        corner_avgs.append({"corner": n, "at_m": cs[0]["at"], "avg_loss_s": round(avg_loss, 3),
                            "avg_brake_diff_m": round(sum(c["brake_diff_m"] for c in cs) / len(cs), 1),
                            "avg_apex_speed_diff": round(sum(c["apex_speed_diff"] for c in cs) / len(cs), 1)})
    corner_avgs.sort(key=lambda c: -c["avg_loss_s"])
    spread = max(times) - best
    return {
        "laps": len(laps), "sim": laps[-1].get("sim"), "track": laps[-1].get("track"), "car": laps[-1].get("car"),
        "best": best, "last": times[-1], "average": round(sum(times) / len(times), 3),
        "consistency_spread_s": round(spread, 3), "lap_times": times,
        "problem_corners": corner_avgs[:4],
    }


def offline_debrief(s: dict) -> list[str]:
    if not s.get("laps"):
        return ["No laps recorded this session yet."]
    out = [f"{s['laps']} laps, best {s['best']:.3f}s, average {s['average']:.3f}s."]
    if s["consistency_spread_s"] > 1.5:
        out.append(f"Lap times spread by {s['consistency_spread_s']:.1f}s; focus on repeating your best lines before pushing harder.")
    else:
        out.append("Consistent lap times; you're ready to push for more pace.")
    for c in s["problem_corners"][:2]:
        bits = []
        if c["avg_brake_diff_m"] > 8:
            bits.append(f"you brake about {c['avg_brake_diff_m']:.0f} m earlier than on your best lap")
        if c["avg_apex_speed_diff"] < -3:
            bits.append(f"you're {-c['avg_apex_speed_diff']:.0f} km/h slower at the apex")
        if bits:
            out.append(f"Corner {c['corner']} ({c['at_m']} m) costs {c['avg_loss_s']:.2f}s a lap: " + " and ".join(bits) + ".")
    return out


def claude_debrief(summary: dict, api_key: str, timeout=30) -> str:
    prompt = (
        "You are a concise, encouraging sim racing engineer. Using only the data below, give the driver "
        "a debrief of at most 5 short sentences: what went well, the one or two biggest time losses and "
        "a concrete thing to try next session. Distances are metres from the start line; speeds km/h. "
        "Don't invent data that isn't there.\n\n" + json.dumps(summary)
    )
    body = json.dumps({"model": MODEL, "max_tokens": 400,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
