"""Update checks for the third-party software Pitwall installs.

Compares what's installed with the latest version on GitHub:
- force feedback drivers built by drivers.Installer: installed commit vs the
  project's newest commit
- the winecarte telemetry bridge: installed release tag vs the latest release

Read-only and fail-soft: a network error is reported per item, never raised.
Nothing is updated automatically; the UI offers an Update button.
"""

from __future__ import annotations

import json
import time
import urllib.request

UA = "Pitwall (+https://github.com/crspytopgn/pitwall)"
CHECK_EVERY_S = 24 * 3600
WINECARTE = "srounce/winecarte"


def _get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def repo_path(url: str) -> str:
    """'https://github.com/owner/repo' -> 'owner/repo'."""
    return url.rstrip("/").split("github.com/", 1)[-1].removesuffix(".git")


def latest_commit(repo: str, fetch=_get) -> dict:
    data = json.loads(fetch(f"https://api.github.com/repos/{repo}/commits?per_page=1"))
    c = data[0]
    return {"sha": c["sha"], "date": (c.get("commit", {}).get("committer", {}) or {}).get("date", "")[:10]}


def latest_release(repo: str, fetch=_get) -> dict:
    data = json.loads(fetch(f"https://api.github.com/repos/{repo}/releases/latest"))
    return {"tag": data.get("tag_name") or "", "date": (data.get("published_at") or "")[:10]}


def check(installed_drivers: dict, driver_info: dict, bridge_installed: bool, bridge_version: str | None,
          fetch=_get, now=time.time) -> dict:
    """installed_drivers: Installer.state(); driver_info: drivers.DRIVERS."""
    items = []
    for did, rec in installed_drivers.items():
        info = driver_info.get(did)
        if not info:
            continue
        item = {"kind": "driver", "id": did, "name": info["name"], "current": rec.get("commit"),
                "latest": None, "date": None, "update": False, "error": None}
        try:
            lc = latest_commit(repo_path(info["repo"]), fetch)
            item["latest"], item["date"] = lc["sha"][:7], lc["date"]
            have = rec.get("sha") or rec.get("commit") or ""
            item["update"] = bool(have) and not lc["sha"].startswith(have)
        except Exception as e:
            item["error"] = f"Couldn't check: {e}"
        items.append(item)
    if bridge_installed:
        item = {"kind": "bridge", "id": "winecarte", "name": "winecarte (telemetry bridge)",
                "current": bridge_version, "latest": None, "date": None, "update": False, "error": None}
        try:
            lr = latest_release(WINECARTE, fetch)
            item["latest"], item["date"] = lr["tag"], lr["date"]
            # Installs from before Pitwall recorded the version count as out of date.
            item["update"] = bool(lr["tag"]) and lr["tag"] != bridge_version
        except Exception as e:
            item["error"] = f"Couldn't check: {e}"
        items.append(item)
    return {"checked": now(), "items": items, "available": [i["id"] for i in items if i["update"]]}


def due(last: dict | None, now=time.time) -> bool:
    return not last or now() - last.get("checked", 0) >= CHECK_EVERY_S
