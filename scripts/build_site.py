#!/usr/bin/env python3
"""Build the GitHub Pages site into _site/ from the same data the plugin uses.

    python3 scripts/build_site.py && python3 -m http.server -d _site
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "py_modules"))

from pitwall import ffb  # noqa: E402

DATA = os.path.join(ROOT, "py_modules", "pitwall", "data")
SITE_SRC = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "_site")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def build(out=OUT):
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(SITE_SRC, out)
    shutil.copy(os.path.join(ROOT, "assets", "wordmark-light.svg"), os.path.join(out, "wordmark.svg"))
    shutil.copy(os.path.join(ROOT, "assets", "mark.svg"), os.path.join(out, "favicon.svg"))
    shutil.copy(os.path.join(ROOT, "assets", "social-preview.png"), os.path.join(out, "social-preview.png"))
    games = load("games.json")
    data = {
        "games": games["games"],
        "sources": games["general_sources"],
        "wheels": load("wheels.json"),
        "tools": load("tools.json"),
        "presets": [{k: p.get(k) for k in ("id", "name", "summary", "values", "bases", "source", "source_note")}
                    for p in ffb.PRESETS],
        "symptoms": [{"label": v["label"], "changes": [[k, d, why] for k, d, why in v["changes"]],
                      "source": v.get("source")} for v in ffb.NUDGES.values()],
    }
    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    open(os.path.join(out, ".nojekyll"), "w").close()
    return out


if __name__ == "__main__":
    print(build())
