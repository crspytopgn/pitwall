"""
Diagnostics bundle for bug reports.

Collects what's needed to debug a problem without asking the user to open a
terminal: OS and kernel, Pitwall version, wheel detection, input devices and
force feedback, telemetry sources and shared-memory maps, pre-race checks,
settings (API key removed) and the tail of Pitwall's logs.

The bundle is saved as a zip in the user's home folder and can be
downloaded from the phone dashboard with a one-time link, then attached to a
GitHub issue that Pitwall pre-fills.
"""

from __future__ import annotations

import glob
import io
import json
import os
import platform
import secrets
import time
import urllib.parse
import zipfile

REPO = "https://github.com/crspytopgn/pitwall"
REDACT_KEYS = {"anthropic_api_key"}
LOG_TAIL_BYTES = 200_000


def _read(path, limit=20_000):
    try:
        with open(path, errors="replace") as f:
            return f.read(limit)
    except OSError:
        return None


def os_release() -> dict:
    out = {}
    for line in (_read("/etc/os-release") or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v.strip('"')
    return out


def redact(settings: dict) -> dict:
    s = json.loads(json.dumps(settings))
    for k in REDACT_KEYS:
        if s.get(k):
            s[k] = "<set, removed>"
    return s


def log_tail(log_dir: str | None) -> dict:
    out = {}
    if not log_dir:
        return out
    files = sorted(glob.glob(os.path.join(log_dir, "*")), key=os.path.getmtime)[-3:]
    for p in files:
        try:
            size = os.path.getsize(p)
            with open(p, "rb") as f:
                f.seek(max(0, size - LOG_TAIL_BYTES))
                out[os.path.basename(p)] = f.read().decode("utf-8", "replace")
        except OSError:
            continue
    return out


def _moza_probe():
    try:
        from .wheels.moza import probe
        return probe()
    except Exception as e:
        return {"error": str(e)}


def collect(version: str, settings: dict, hub=None, wheel=None, checks=None, log_dir=None, extra=None) -> dict:
    from .health import input_wheels
    rel = os_release()
    info = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "pitwall_version": version,
        "os": rel.get("PRETTY_NAME") or platform.platform(),
        "os_build": rel.get("BUILD_ID") or rel.get("VERSION_ID"),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "machine": _read("/sys/class/dmi/id/product_name", 200),
        "wheel": {"name": getattr(wheel, "name", None), "brand": getattr(wheel, "brand", None),
                  "error": getattr(wheel, "error", None)} if wheel else None,
        "input_wheels": input_wheels(),
        "pidff_loaded": os.path.isdir("/sys/module/hid_universal_pidff"),
        "serial_by_id": sorted(os.listdir("/dev/serial/by-id")) if os.path.isdir("/dev/serial/by-id") else [],
        "tty_acm": sorted(os.path.basename(p) for p in glob.glob("/dev/ttyACM*")),
        "moza_probe": _moza_probe(),
        "shm_maps": sorted(n for n in os.listdir("/dev/shm") if any(k in n for k in ("acpmf", "pcars", "rFactor", "LMU", "R3E")))
        if os.path.isdir("/dev/shm") else [],
        "settings": redact(settings),
        "checks": checks,
    }
    if hub:
        st = hub.status()
        info["telemetry"] = {k: st.get(k) for k in ("receiving", "sim", "car", "track", "sources", "session_laps")}
        info["strategy"] = hub.strategy.report()
    if extra:
        info.update(extra)
    return info


def summary_text(info: dict) -> str:
    t = info.get("telemetry") or {}
    w = info.get("wheel") or {}
    lines = [
        f"Pitwall {info.get('pitwall_version')} on {info.get('os')} (kernel {info.get('kernel')})",
        f"Machine: {info.get('machine') or 'unknown'}",
        f"Wheel: {w.get('name') or 'none detected'}; FFB driver loaded: {info.get('pidff_loaded')}",
        f"Telemetry: {t.get('sim') or 'none'}; receiving: {t.get('receiving')}",
    ]
    mp = info.get("moza_probe") or {}
    if mp.get("devices"):
        lines.append("MOZA USB: " + "; ".join(f"{d.get('name') or d.get('pid')} (serial port: {'yes' if d.get('serial') else 'no'}"
                                              f"{', Xbox mode' if d.get('xbox') else ''})" for d in mp["devices"]))
    elif "state" in mp:
        lines.append("MOZA USB: none found")
    failed = [c["title"] for c in (info.get("checks") or []) if c.get("ok") is False]
    if failed:
        lines.append("Failed checks: " + "; ".join(failed))
    return "\n".join(lines)


def write_zip(info: dict, logs: dict, out_dir: str, uid=None, gid=None) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, time.strftime("pitwall-diagnostics-%Y%m%d-%H%M%S.zip"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("summary.txt", summary_text(info) + "\n")
        z.writestr("diagnostics.json", json.dumps(info, indent=2, default=str))
        for name, text in logs.items():
            z.writestr(f"logs/{name}", text)
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    if uid is not None:
        try:
            os.chown(path, uid, gid if gid is not None else uid)
        except OSError:
            pass
    return path


def issue_url(info: dict) -> str:
    """Pre-filled GitHub issue (issue forms accept field ids as query params)."""
    q = {
        "template": "bug_report.yml",
        "title": "[bug] ",
        "device": info.get("machine") and f"{info.get('machine')}, {info.get('os')}" or info.get("os"),
        "version": info.get("pitwall_version"),
        "wheel": (info.get("wheel") or {}).get("name") or "",
        "sim": (info.get("telemetry") or {}).get("sim") or "",
        "log": summary_text(info) + "\n\n(Full diagnostics zip attached.)",
    }
    return f"{REPO}/issues/new?" + urllib.parse.urlencode({k: v for k, v in q.items() if v})


class DownloadTokens:
    """One-time, short-lived links so the zip can be fetched from a phone."""

    def __init__(self, ttl=600):
        self.ttl = ttl
        self.tokens: dict[str, tuple[str, float]] = {}

    def issue(self, path: str) -> str:
        tok = secrets.token_urlsafe(16)
        self.tokens[tok] = (path, time.time() + self.ttl)
        return tok

    def take(self, tok: str) -> str | None:
        item = self.tokens.pop(tok, None)
        if not item or item[1] < time.time():
            return None
        return item[0]
