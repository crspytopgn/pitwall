"""Steam integration for standalone Pitwall (no Decky).

Inside Decky, Pitwall talks to the Steam client directly. Outside it, this
module does the same jobs from Steam's files and the process list:

- which game is running: Steam starts every game through its `reaper` helper
  with `SteamLaunch AppId=<id>` on the command line
- game names: steamapps/appmanifest_<id>.acf in each library folder
- launch options: userdata/<account>/config/localconfig.vdf

Steam keeps localconfig.vdf in memory and rewrites it when it exits, so
launch options are only written while Steam is closed. Changes made while it's
running are queued and applied as soon as Steam exits. A backup of the file is
kept before every write.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import time

STEAMID64_BASE = 76561197960265728


# ------------------------------------------------------------------ VDF text
class VdfError(ValueError):
    pass


def _tokens(text: str):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "/" and text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
        elif c in "{}":
            yield c
            i += 1
        elif c == '"':
            j, out = i + 1, []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(text[j + 1], text[j + 1]))
                    j += 2
                else:
                    out.append(text[j])
                    j += 1
            if j >= n:
                raise VdfError("unterminated string")
            yield ("s", "".join(out))
            i = j + 1
        else:  # unquoted token (rare in Steam's files) or a [$CONDITION]
            j = i
            while j < n and text[j] not in ' \t\r\n{}"':
                j += 1
            tok = text[i:j]
            if not (tok.startswith("[") and tok.endswith("]")):
                yield ("s", tok)
            i = j


def loads(text: str) -> list:
    """Parse VDF into a list of [key, value] pairs, where value is a str or a
    nested list. Order and duplicate keys are kept so a write changes nothing
    but the edited value."""
    toks = list(_tokens(text))
    pos = 0

    def block(top: bool) -> list:
        nonlocal pos
        out = []
        while pos < len(toks):
            t = toks[pos]
            if t == "}":
                if top:
                    raise VdfError("unexpected }")
                pos += 1
                return out
            if t == "{" or t[0] != "s":
                raise VdfError("expected a key")
            key = t[1]
            pos += 1
            if pos >= len(toks):
                raise VdfError("key without value")
            v = toks[pos]
            if v == "{":
                pos += 1
                out.append([key, block(False)])
            elif v == "}":
                raise VdfError("key without value")
            else:
                out.append([key, v[1]])
                pos += 1
        if not top:
            raise VdfError("unclosed {")
        return out

    return block(True)


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def dumps(tree: list, depth: int = 0) -> str:
    ind = "\t" * depth
    out = []
    for k, v in tree:
        if isinstance(v, list):
            out.append(f'{ind}"{_esc(k)}"\n{ind}{{\n{dumps(v, depth + 1)}{ind}}}\n')
        else:
            out.append(f'{ind}"{_esc(k)}"\t\t"{_esc(v)}"\n')
    return "".join(out)


def get(tree: list, *path: str, create: bool = False):
    """Walk keys case-insensitively (Steam isn't consistent about case)."""
    node = tree
    for key in path:
        found = None
        for pair in node:
            if pair[0].lower() == key.lower() and isinstance(pair[1], list):
                found = pair[1]
                break
        if found is None:
            if not create:
                return None
            found = []
            node.append([key, found])
        node = found
    return node


def value(node: list | None, key: str) -> str | None:
    for k, v in node or []:
        if k.lower() == key.lower() and isinstance(v, str):
            return v
    return None


def set_value(node: list, key: str, val: str):
    for pair in node:
        if pair[0].lower() == key.lower() and isinstance(pair[1], str):
            pair[1] = val
            return
    node.append([key, val])


# --------------------------------------------------------------- locations
def steam_roots(home: str) -> list[str]:
    cands = [os.path.join(home, ".local/share/Steam"), os.path.join(home, ".steam/steam"),
             os.path.join(home, ".var/app/com.valvesoftware.Steam/.local/share/Steam")]
    seen, out = set(), []
    for c in cands:
        r = os.path.realpath(c)
        if os.path.isdir(os.path.join(r, "steamapps")) or os.path.isdir(os.path.join(r, "userdata")):
            if r not in seen:
                seen.add(r)
                out.append(r)
    return out


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def library_folders(root: str) -> list[str]:
    out = [root]
    txt = _read(os.path.join(root, "steamapps/libraryfolders.vdf"))
    if txt:
        try:
            lf = get(loads(txt), "libraryfolders") or []
            for _k, v in lf:
                p = value(v, "path") if isinstance(v, list) else None
                if p and os.path.realpath(p) not in [os.path.realpath(x) for x in out]:
                    out.append(p)
        except VdfError:
            pass
    return out


def app_name(home: str, appid: str) -> str | None:
    if not str(appid).isdigit():
        return None
    for root in steam_roots(home):
        for lib in library_folders(root):
            txt = _read(os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf"))
            if txt:
                try:
                    return value(get(loads(txt), "AppState"), "name")
                except VdfError:
                    return None
    return None


def localconfig_path(home: str) -> str | None:
    """The most recently signed-in account's localconfig.vdf."""
    for root in steam_roots(home):
        users = _read(os.path.join(root, "config/loginusers.vdf"))
        if users:
            try:
                for sid, info in get(loads(users), "users") or []:
                    if isinstance(info, list) and value(info, "MostRecent") == "1" and sid.isdigit():
                        p = os.path.join(root, "userdata", str(int(sid) - STEAMID64_BASE), "config/localconfig.vdf")
                        if os.path.exists(p):
                            return p
            except VdfError:
                pass
        found = sorted(glob.glob(os.path.join(root, "userdata/*/config/localconfig.vdf")), key=os.path.getmtime, reverse=True)
        if found:
            return found[0]
    return None


# --------------------------------------------------------------- processes
def _cmdlines(proc: str = "/proc"):
    for pid in os.listdir(proc):
        if not pid.isdigit():
            continue
        try:
            with open(os.path.join(proc, pid, "cmdline"), "rb") as f:
                yield pid, f.read().split(b"\0")
        except OSError:
            continue


def running_game(proc: str = "/proc") -> str | None:
    """App ID of the game Steam is running, from its reaper process."""
    for _pid, args in _cmdlines(proc):
        if b"SteamLaunch" not in args:
            continue
        for a in args:
            m = re.fullmatch(rb"AppId=(\d+)", a)
            if m and m.group(1) != b"0":
                return m.group(1).decode()
    return None


def steam_running(proc: str = "/proc") -> bool:
    for pid in os.listdir(proc):
        if not pid.isdigit():
            continue
        try:
            with open(os.path.join(proc, pid, "comm")) as f:
                comm = f.read().strip()
        except OSError:
            continue
        if comm in ("steam", "steamwebhelper"):
            return True
    return False


# ----------------------------------------------------------- launch options
class LaunchOptions:
    """Read launch options from localconfig.vdf; write them only while Steam is
    closed, queueing changes made while it's running."""

    def __init__(self, home: str, queue_file: str, proc: str = "/proc", uid: int | None = None, gid: int | None = None):
        self.home, self.queue_file, self.proc = home, queue_file, proc
        self.uid, self.gid = uid, gid

    def _queue(self) -> dict:
        try:
            with open(self.queue_file) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_queue(self, q: dict):
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        tmp = self.queue_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(q, f)
        os.replace(tmp, self.queue_file)

    def get(self, appid: str) -> str | None:
        """Pending value if one is queued, else what Steam has saved; None if unreadable."""
        appid = str(appid)
        q = self._queue()
        if appid in q:
            return q[appid]
        path = localconfig_path(self.home)
        txt = _read(path) if path else None
        if txt is None:
            return None
        try:
            app = get(loads(txt), "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", appid)
        except VdfError:
            return None
        return value(app, "LaunchOptions") or ""

    def set(self, appid: str, opts: str) -> dict:
        appid = str(appid)
        if not appid.isdigit():
            return {"ok": False, "applied": False, "message": "Unknown game."}
        q = self._queue()
        q[appid] = opts
        self._save_queue(q)
        if steam_running(self.proc):
            return {"ok": True, "applied": False,
                    "message": "Saved. Steam is open, so Pitwall will apply this when you exit Steam "
                               "(Steam menu, Exit). Or paste it into the game's Properties, Launch options."}
        return self.flush()

    def pending(self) -> dict:
        return self._queue()

    def flush(self) -> dict:
        """Write queued launch options into localconfig.vdf (Steam must be closed)."""
        q = self._queue()
        if not q:
            return {"ok": True, "applied": False, "message": "Nothing to apply."}
        if steam_running(self.proc):
            return {"ok": True, "applied": False, "message": "Waiting for Steam to close."}
        path = localconfig_path(self.home)
        txt = _read(path) if path else None
        if txt is None:
            return {"ok": False, "applied": False, "message": "Couldn't find Steam's settings for your account."}
        try:
            tree = loads(txt)
        except VdfError as e:
            return {"ok": False, "applied": False, "message": f"Steam's settings file couldn't be read ({e}); nothing changed."}
        for appid, opts in q.items():
            node = get(tree, "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", appid, create=True)
            set_value(node, "LaunchOptions", opts)
        backup = path + ".pitwall-backup"
        try:
            shutil.copy2(path, backup)
            tmp = path + ".pitwall-tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(dumps(tree))
            st = os.stat(path)
            os.chmod(tmp, st.st_mode & 0o777)
            if self.uid is not None:
                os.chown(tmp, self.uid, self.gid if self.gid is not None else st.st_gid)
                os.chown(backup, self.uid, self.gid if self.gid is not None else st.st_gid)
            os.replace(tmp, path)
        except OSError as e:
            return {"ok": False, "applied": False, "message": f"Couldn't write Steam's settings: {e.strerror}"}
        self._save_queue({})
        return {"ok": True, "applied": True, "message": f"Launch options applied for {len(q)} game(s).", "at": time.time()}
