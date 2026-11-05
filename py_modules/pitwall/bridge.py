"""
One-tap telemetry bridge setup for shared-memory sims under Proton.

Uses winecarte (https://github.com/srounce/winecarte): a native launcher plus
wine2linux.exe that runs inside the game's Proton prefix and mirrors the
game's shared memory into /dev/shm. Pitwall downloads the latest release
from GitHub into ~/.local/share/pitwall/bin and builds the Steam launch
option; the frontend applies it to the game.

Supported by winecarte: Assetto Corsa, ACC, AC EVO, AC Rally, Le Mans Ultimate,
rFactor 2, Project CARS 2, Automobilista 2.
"""

from __future__ import annotations

import io
import json
import os
import shlex
import stat
import tarfile
import urllib.request
import zipfile

API = "https://api.github.com/repos/srounce/winecarte/releases/latest"
UA = "Pitwall (+https://github.com/crspytopgn/pitwall)"
NEEDED = ("winecarte-run", "wine2linux.exe")
SUPPORTED_APPIDS = {244210, 805550, 3058630, 3917090, 2399420, 365960, 378860, 1066890}


def bin_dir(home: str) -> str:
    return os.path.join(home, ".local", "share", "pitwall", "bin")


def installed(home: str) -> bool:
    d = bin_dir(home)
    return all(os.path.exists(os.path.join(d, n)) for n in NEEDED)


def _get(url: str, timeout=30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _extract(name: str, data: bytes) -> dict[str, bytes]:
    """Pull the needed files out of a release asset (archive or single file)."""
    out: dict[str, bytes] = {}
    base = os.path.basename(name)
    if base in NEEDED:
        out[base] = data
    elif name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for m in z.namelist():
                if os.path.basename(m) in NEEDED:
                    out[os.path.basename(m)] = z.read(m)
    elif any(name.endswith(s) for s in (".tar.gz", ".tgz", ".tar.xz", ".tar.zst", ".tar")):
        try:
            with tarfile.open(fileobj=io.BytesIO(data)) as t:
                for m in t.getmembers():
                    if m.isfile() and os.path.basename(m.name) in NEEDED:
                        f = t.extractfile(m)
                        if f:
                            out[os.path.basename(m.name)] = f.read()
        except tarfile.TarError:
            pass
    return out


def install(home: str, uid: int | None = None, gid: int | None = None, fetch=_get) -> dict:
    try:
        rel = json.loads(fetch(API))
    except Exception as e:
        return {"ok": False, "message": f"Couldn't reach GitHub to download winecarte: {e}"}
    found: dict[str, bytes] = {}
    for a in rel.get("assets", []):
        url, name = a.get("browser_download_url"), a.get("name", "")
        if not url:
            continue
        if not (name in NEEDED or name.endswith((".zip", ".tar.gz", ".tgz", ".tar.xz", ".tar"))):
            continue
        try:
            found.update(_extract(name, fetch(url)))
        except Exception:
            continue
        if all(n in found for n in NEEDED):
            break
    missing = [n for n in NEEDED if n not in found]
    if missing:
        return {"ok": False, "message": f"The latest winecarte release didn't contain {', '.join(missing)}."}
    d = bin_dir(home)
    os.makedirs(d, exist_ok=True)
    for n, data in found.items():
        p = os.path.join(d, n)
        with open(p, "wb") as f:
            f.write(data)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if uid is not None:
        for p in (os.path.dirname(d), d, *(os.path.join(d, n) for n in NEEDED)):
            try:
                os.chown(p, uid, gid if gid is not None else uid)
            except OSError:
                pass
    return {"ok": True, "message": f"winecarte {rel.get('tag_name', '')} installed.".replace("  ", " "),
            "version": rel.get("tag_name")}


def launch_prefix(home: str) -> str:
    d = bin_dir(home)
    return (f"WINECARTE_WINE2LINUX_EXE={shlex.quote(os.path.join(d, 'wine2linux.exe'))} "
            f"{shlex.quote(os.path.join(d, 'winecarte-run'))}")


def merge_launch_options(current: str, prefix: str) -> str:
    """Insert the bridge before %command%, keeping whatever the user had."""
    current = (current or "").strip()
    if "winecarte-run" in current:
        return current
    if "%command%" in current:
        return current.replace("%command%", f"{prefix} %command%", 1)
    return f"{prefix} %command% {current}".strip()


def remove_from_launch_options(current: str, prefix: str) -> str:
    cur = (current or "").replace(prefix + " ", "")
    return "" if cur.strip() == "%command%" else cur.strip()
