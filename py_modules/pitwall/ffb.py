"""
Force feedback feel: sourced starting presets plus a "feel tuner" that turns
what the driver feels into small, reversible setting changes.

Principle behind the presets: in sims with full tyre physics (BeamNG, AC,
ACC, AMS2, rF2) the game already computes the steering forces, so base-side
effects such as spring and damper are artificial filters layered on top.
"Pure" removes them; the others add a little weight back, which helps lower
torque bases like the R3/R5. Every preset cites where its numbers come from.
"""

from __future__ import annotations

PRESETS = [
    {
        "id": "pure",
        "name": "Pure (game physics only)",
        "summary": "No added spring, damper or friction: you feel only what the sim calculates. Most detail, lightest feel.",
        "values": {"ffb_strength": 100, "road_sensitivity": 10, "spring": 0, "damper": 0, "friction": 0,
                   "inertia": 100, "speed": 200, "speed_damping": 0},
        "source": "https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa",
        "source_note": "MOZA keeps spring at 0% because the sim handles centring; Pitwall extends the same idea to the other base effects.",
    },
    # MOZA's own per-base recommendations (written for Assetto Corsa). Speed-dependent
    # damping 20% from 90 km/h is the guide's general setting for every base.
    {
        "id": "moza_r3_r5",
        "name": "MOZA's R3/R5 recommendation",
        "summary": "MOZA's published starting point for R3/R5 bases.",
        "values": {"rotation": 900, "road_sensitivity": 8, "ffb_strength": 100, "speed": 120, "spring": 0,
                   "damper": 60, "torque": 100, "inertia": 140, "friction": 25,
                   "speed_damping": 20, "speed_damping_point": 90},
        "bases": ["R3", "R5"],
        "source": "https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa",
        "source_note": "Official MOZA guide, R3/R5 column.",
    },
    {
        "id": "moza_r9_r12",
        "name": "MOZA's R9/R12 recommendation",
        "summary": "MOZA's published starting point for R9/R12 bases.",
        "values": {"rotation": 900, "road_sensitivity": 9, "ffb_strength": 92, "speed": 120, "spring": 0,
                   "damper": 50, "torque": 90, "inertia": 150, "friction": 20,
                   "speed_damping": 20, "speed_damping_point": 90},
        "bases": ["R9", "R12"],
        "source": "https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa",
        "source_note": "Official MOZA guide, R9/R12 column (FFB intensity given as 90-95%; Pitwall uses 92%).",
    },
    {
        "id": "moza_r16_r21",
        "name": "MOZA's R16/R21 recommendation",
        "summary": "MOZA's published starting point for R16/R21 bases.",
        "values": {"rotation": 900, "road_sensitivity": 10, "ffb_strength": 75, "speed": 120, "spring": 0,
                   "damper": 40, "torque": 80, "inertia": 160, "friction": 15,
                   "speed_damping": 20, "speed_damping_point": 90},
        "bases": ["R16", "R21", "R25"],
        "source": "https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa",
        "source_note": "Official MOZA guide, R16/R21 column (FFB intensity given as 70-80%; Pitwall uses 75%). Pitwall also uses it for the R25 until MOZA publishes figures for it.",
    },
    {
        "id": "weighted",
        "name": "Weighted, no damping",
        "summary": "Heavy natural inertia and friction for a planted feel, no damper so detail isn't smothered.",
        "values": {"road_sensitivity": 4, "ffb_strength": 100, "speed": 200, "spring": 0, "damper": 0,
                   "torque": 100, "inertia": 500, "friction": 100, "speed_damping": 0},
        "source": "https://simracingcockpit.gg/moza-ffb-settings-for-iracing-r5-r9-r12-r16-and-r21/",
        "source_note": "Settings a MOZA Creator Program driver shared for an R5 (from MOZA's R5 video), as summarised in the linked guide.",
    },
]

# Symptom -> list of (setting, delta, reason). Deltas are in UI units.
NUDGES = {
    "too_light": {
        "label": "Wheel feels light or vague",
        "changes": [("inertia", +50, "adds simulated mass so the wheel resists quick movements"),
                    ("friction", +5, "adds a little mechanical drag")],
        "source": "https://simracingcockpit.gg/f1-24-moza-settings/",
    },
    "too_heavy": {
        "label": "Too heavy, tiring in slow corners",
        "changes": [("ffb_strength", -10, "reduces overall force"),
                    ("friction", -5, "less drag at low speed")],
        "source": None,
    },
    "oscillates": {
        "label": "Wheel oscillates on straights or when I let go",
        "changes": [("damper", +10, "damps the swinging"),
                    ("speed_damping", +10, "extra damping only at high speed"),
                    ("speed", -20, "caps how fast the wheel can spin")],
        "source": "https://eu.mozaracing.com/blogs/blog/moza-settings-guide-for-assetto-corsa",
    },
    "numb_road": {
        "label": "Can't feel the road, kerbs or grip",
        "changes": [("road_sensitivity", +1, "more road surface detail"),
                    ("damper", -10, "damper can smother small details")],
        "source": "https://simracingsetup.com/f1-23/f1-23-best-moza-wheel-settings/",
    },
    "rattly": {
        "label": "Too much rattle and buzzing",
        "changes": [("road_sensitivity", -1, "less road surface noise")],
        "source": "https://docs.beamng.com/support/hardware/steering_wheel_setup/",
        "game_tip": {"beamng": "In BeamNG, raise Smoothing a little in the steering binding's force feedback settings."},
    },
    "flat_in_corners": {
        "label": "Forces feel flat or the same in every corner",
        "changes": [("ffb_strength", -10, "leaves headroom so peaks aren't cut off (clipping)")],
        "source": None,
        "game_tip": {"beamng": "Lower BeamNG's force feedback Strength for this car until big and small forces feel different again.",
                     "_": "Lower the in-game FFB gain; flat-feeling peaks usually mean the signal is clipping."},
    },
}


def clamp_values(values: dict, ranges: dict) -> dict:
    out = {}
    for k, v in values.items():
        r = ranges.get(k)
        if r is None:
            continue           # this wheel doesn't have the setting
        out[k] = max(r["min"], min(r["max"], v))
    return out


def preset_values(preset_id: str, ranges: dict) -> dict | None:
    p = next((p for p in PRESETS if p["id"] == preset_id), None)
    return clamp_values(p["values"], ranges) if p else None


def nudge(symptom: str, current: dict, ranges: dict, sim: str | None = None) -> dict | None:
    n = NUDGES.get(symptom)
    if not n:
        return None
    new, changes = {}, []
    for key, delta, why in n["changes"]:
        if key not in current or key not in ranges:
            continue
        r = ranges[key]
        v = max(r["min"], min(r["max"], current[key] + delta))
        if v != current[key]:
            new[key] = v
            changes.append({"key": key, "label": r.get("label", key), "from": current[key], "to": v, "why": why})
    tips = n.get("game_tip") or {}
    tip = tips.get(sim or "") or tips.get("_")
    return {"values": new, "changes": changes, "tip": tip, "source": n.get("source")}


def preset_for_base(model: str | None) -> str:
    """Best starting preset for a MOZA base model like 'R3'; 'pure' otherwise."""
    if model:
        for p in PRESETS:
            if model.upper() in p.get("bases", []):
                return p["id"]
    return "pure"


def catalogue() -> dict:
    return {
        "presets": [{k: p[k] for k in ("id", "name", "summary", "source", "source_note")} for p in PRESETS],
        "symptoms": [{"id": k, "label": v["label"]} for k, v in NUDGES.items()],
    }
