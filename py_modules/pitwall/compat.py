"""
Compatibility guide: curated per-game knowledge (data/games.json) plus live
ratings fetched from the sources that matter most on SteamOS:

- Valve's Steam Deck compatibility rating (official testing)
- ProtonDB summary tier (crowd-sourced reports)
- Are We Anti-Cheat Yet (anti-cheat status, the usual blocker for online sims)

Live data is cached on disk for 24 hours and every fetch fails soft: if the
network is down the curated data is still shown.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import time
import urllib.request

DATA = os.path.join(os.path.dirname(__file__), "data", "games.json")
CACHE_TTL = 24 * 3600
UA = "Pitwall/0.2 (+https://github.com/crspytopgn/pitwall)"

PROTONDB = "https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
DECK = "https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport?nAppID={appid}"
AWACY = "https://raw.githubusercontent.com/AreWeAntiCheatYet/AreWeAntiCheatYet/master/games.json"
DECK_CATEGORIES = {0: "Unknown", 1: "Unsupported", 2: "Playable", 3: "Verified"}


def load_games() -> dict:
    with open(DATA) as f:
        return json.load(f)


def _get_json(url: str, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


class LiveRatings:
    def __init__(self, cache_dir: str):
        self.path = os.path.join(cache_dir, "compat_cache.json")
        try:
            with open(self.path) as f:
                self.cache = json.load(f)
        except (OSError, ValueError):
            self.cache = {}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.cache, f)
        os.replace(tmp, self.path)

    def _cached(self, key, fetch):
        hit = self.cache.get(key)
        if hit and time.time() - hit["t"] < CACHE_TTL:
            return hit["v"]
        try:
            v = fetch()
        except Exception:
            return hit["v"] if hit else None   # stale beats nothing
        self.cache[key] = {"t": time.time(), "v": v}
        self._save()
        return v

    def protondb(self, appid: int):
        def f():
            d = _get_json(PROTONDB.format(appid=appid))
            return {k: d.get(k) for k in ("tier", "trendingTier", "bestReportedTier", "confidence", "total") if k in d}
        return self._cached(f"pdb:{appid}", f)

    def deck(self, appid: int):
        def f():
            d = _get_json(DECK.format(appid=appid))
            res = d.get("results") or {}
            cat = res.get("resolved_category")
            notes = []
            for item in res.get("resolved_items") or []:
                tok = item.get("loc_token") or ""
                if tok:
                    notes.append(tok.replace("#SteamDeckVerified_TestResult_", "").replace("_", " "))
            return {"category": DECK_CATEGORIES.get(cat, "Unknown"), "notes": notes}
        return self._cached(f"deck:{appid}", f)

    def anticheat(self):
        def f():
            out = {}
            for g in _get_json(AWACY, timeout=15):
                sid = (g.get("storeIds") or {}).get("steam")
                entry = {"status": g.get("status"), "anticheats": g.get("anticheats"), "name": g.get("name")}
                if sid:
                    out[f"id:{sid}"] = entry
                out[f"name:{(g.get('name') or '').lower()}"] = entry
            return out
        return self._cached("awacy", f)


# ------------------------------------------------------------ Steam library
def steam_roots(home: str) -> list[str]:
    roots = []
    for base in (os.path.join(home, ".local/share/Steam"), os.path.join(home, ".steam/steam")):
        vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            roots.append(base)
            with open(vdf, errors="ignore") as f:
                roots += re.findall(r'"path"\s+"([^"]+)"', f.read())
    seen, out = set(), []
    for r in roots:
        r = os.path.realpath(r)
        if r not in seen and os.path.isdir(os.path.join(r, "steamapps")):
            seen.add(r)
            out.append(r)
    return out


def installed_appids(home: str) -> dict[int, str]:
    found = {}
    for root in steam_roots(home):
        for m in glob.glob(os.path.join(root, "steamapps", "appmanifest_*.acf")):
            try:
                found[int(re.search(r"appmanifest_(\d+)", m).group(1))] = root
            except (AttributeError, ValueError):
                pass
    return found


def prefix_path(home: str, appid: int) -> str | None:
    for root in steam_roots(home):
        p = os.path.join(root, "steamapps", "compatdata", str(appid), "pfx")
        if os.path.isdir(p):
            return p
    return None


# --------------------------------------------------------------- auto setup
def dr2_enable_udp(home: str, port: int = 20777) -> dict:
    """Enable DiRT Rally 2.0's UDP telemetry (extradata=3) in its Proton prefix."""
    pfx = prefix_path(home, 690790)
    if not pfx:
        return {"ok": False, "message": "DiRT Rally 2.0's Proton prefix wasn't found. Launch the game once, then try again."}
    cands = glob.glob(os.path.join(pfx, "drive_c/users/*/Documents/My Games/DiRT Rally 2.0/hardwaresettings/hardware_settings_config*.xml"))
    if not cands:
        return {"ok": False, "message": "hardware_settings_config.xml not found. Launch the game once to create it."}
    changed = []
    for path in cands:
        with open(path, encoding="utf-8", errors="ignore") as f:
            xml = f.read()
        new_tag = f'<udp enabled="true" extradata="3" ip="127.0.0.1" port="{port}" delay="1" />'
        if re.search(r"<udp\b[^>]*/>", xml):
            new = re.sub(r"<udp\b[^>]*/>", new_tag, xml, count=1)
        elif "</motion_platform>" in xml:
            new = xml.replace("</motion_platform>", f"  {new_tag}\n\t</motion_platform>", 1)
        else:
            continue
        if new != xml:
            shutil.copy2(path, path + ".pitwall.bak")
            st = os.stat(path)
            try:
                os.chown(path + ".pitwall.bak", st.st_uid, st.st_gid)
            except OSError:
                pass
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            changed.append(os.path.basename(path))
    if not changed:
        return {"ok": True, "message": "Telemetry was already enabled."}
    return {"ok": True, "message": f"Enabled UDP telemetry in {', '.join(changed)} (backup saved as .pitwall.bak). Restart the game if it's running."}


AUTO_SETUP = {"dr2_udp": dr2_enable_udp}


# ------------------------------------------------------------------- report
class Compat:
    def __init__(self, home: str, cache_dir: str):
        self.home = home
        self.live = LiveRatings(cache_dir)
        self.data = load_games()

    def find(self, appid: str | int | None = None, name: str | None = None) -> dict | None:
        for g in self.data["games"]:
            if appid is not None and g.get("steam_appid") and str(g["steam_appid"]) == str(appid):
                return g
        if name:
            n = name.lower()
            for g in self.data["games"]:
                if g.get("match_name", g["name"]).lower() in n:
                    return g
        return None

    def overview(self) -> list[dict]:
        inst = installed_appids(self.home)
        out = []
        for g in self.data["games"]:
            out.append({"id": g["id"], "name": g["name"], "status": g["status"],
                        "installed": bool(g.get("steam_appid") and g["steam_appid"] in inst),
                        "telemetry": g["telemetry"].get("quality")})
        order = {"works": 0, "setup": 1, "community": 2, "broken": 3}
        return sorted(out, key=lambda x: (not x["installed"], order.get(x["status"], 9), x["name"]))

    def detail(self, game_id: str, online: bool = True) -> dict | None:
        g = next((x for x in self.data["games"] if x["id"] == game_id), None)
        if not g:
            return None
        out = dict(g)
        appid = g.get("steam_appid")
        if online:
            if appid:
                out["live_protondb"] = self.live.protondb(appid)
                out["live_deck"] = self.live.deck(appid)
            ac = self.live.anticheat() or {}
            hit = ac.get(f"id:{appid}") if appid else None
            hit = hit or ac.get(f"name:{g.get('match_name', g['name']).lower()}")
            out["live_anticheat"] = hit
        out["installed"] = bool(appid and appid in installed_appids(self.home))
        return out

    def run_auto_setup(self, game_id: str) -> dict:
        g = next((x for x in self.data["games"] if x["id"] == game_id), None)
        fn = AUTO_SETUP.get((g or {}).get("auto_setup"))
        if not fn:
            return {"ok": False, "message": "No automatic setup for this game; follow the steps shown."}
        return fn(self.home)
