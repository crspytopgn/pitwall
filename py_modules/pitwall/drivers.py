"""Install community force feedback drivers on SteamOS.

Some wheels need a kernel driver that isn't in SteamOS's kernel (or isn't in
it yet). This builds the driver from its official repository for the exact
running kernel, the way each project documents for Arch-based systems, and
installs it under /usr/lib/modules/<kernel>/updates/pitwall so it takes
priority over the in-kernel module.

SteamOS's system partition is read-only and is replaced by SteamOS updates, so:
- the read-only flag is lifted only for the install and put back afterwards
- an update removes the driver; Pitwall records what it installed and offers
  to reinstall when the kernel changes

Only SteamOS is handled automatically. Elsewhere, Pitwall shows the project's
own instructions.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
import time

MOD_SUBDIR = "updates/pitwall"

# Each project's repository, the modules it builds and anything else it needs
# installed, from the project's own README / Makefile / install script.
DRIVERS = {
    "universal-pidff": {
        "name": "hid-universal-pidff", "repo": "https://github.com/JacKeTUs/universal-pidff",
        "for": "MOZA, Cammus, PXN, VRS, Asetek, Turtle Beach, FFBeast and other direct drive bases",
        "modules": [("hid_universal_pidff.ko", "hid_universal_pidff.ko")], "load": ["hid_universal_pidff"],
        "unload": [], "builtin_name": "hid-universal-pidff.ko", "submodules": False,
    },
    "new-lg4ff": {
        "name": "new-lg4ff", "repo": "https://github.com/berarma/new-lg4ff",
        "for": "Logitech G25, G27, G29, G923 (PlayStation), DFGT, DFP, MOMO",
        # Installed under the in-kernel module's name so it replaces it, as the project's DKMS setup does.
        "modules": [("hid-logitech-new.ko", "hid-logitech.ko")], "load": ["hid-logitech"],
        "unload": ["hid_logitech_new", "hid_logitech"], "restore": ["hid-logitech"],
        "builtin_name": "hid-logitech.ko", "submodules": False,
    },
    "hid-fanatecff": {
        "name": "hid-fanatecff", "repo": "https://github.com/gotzl/hid-fanatecff",
        "for": "Fanatec CSL DD, DD Pro, ClubSport DD, Podium, CSL Elite, ClubSport V2/V2.5, CSR Elite",
        "modules": [("hid-fanatec.ko", "hid-fanatec.ko")], "load": ["hid-fanatec"], "unload": ["hid_fanatec"],
        "rules": [("fanatec.rules", "99-fanatec.rules")], "version_placeholder": "#VERSION#",
        "builtin_name": None, "submodules": False,
    },
    "hid-tmff2": {
        "name": "hid-tmff2", "repo": "https://github.com/Kimplul/hid-tmff2",
        "for": "Thrustmaster T300RS, T248, TX, TS-XW, TS-PC",
        "modules": [("hid-tmff-new.ko", "hid-tmff-new.ko"), ("deps/hid-tminit/hid-tminit.ko", "hid-tminit.ko")],
        "load": ["hid-tminit", "hid-tmff-new"], "unload": ["hid_tmff_new", "hid_tminit"],
        "rules": [("udev/71-thrustmaster-steamdeck.rules", "71-thrustmaster-steamdeck.rules")],
        "make_all": True, "builtin_name": None, "submodules": True,
    },
    "simagic-ff": {
        "name": "simagic-ff", "repo": "https://github.com/JacKeTUs/simagic-ff",
        "for": "Simagic Alpha, Alpha Mini, Alpha Ultimate, EVO (firmware v159 and later)",
        "modules": [("hid-simagic-ff.ko", "hid-simagic-ff.ko")], "load": ["hid-simagic-ff"],
        "unload": ["hid_simagic_ff"], "builtin_name": None, "submodules": False,
    },
}


def driver_for(known: dict | None, has_universal_pidff: bool) -> str | None:
    """Which installable driver a wheel from the support table needs, if any."""
    if not known:
        return None
    drv = (known.get("driver") or "")
    url = known.get("driver_url") or ""
    if "universal-pidff" in drv:
        return None if has_universal_pidff else "universal-pidff"
    if "new-lg4ff" in url:
        return "new-lg4ff"
    if "hid-fanatecff" in drv:
        return "hid-fanatecff"
    if "hid-tmff2" in drv:
        return "hid-tmff2"
    if "simagic-ff" in drv:
        return "simagic-ff"
    return None


def is_steamos(root: str = "/") -> bool:
    try:
        with open(os.path.join(root, "etc/os-release")) as f:
            txt = f.read()
    except OSError:
        return False
    return any(line.strip() in ("ID=steamos", 'ID="steamos"') for line in txt.splitlines())


def module_dir(krel: str, root: str = "/") -> str:
    return os.path.join(root, "usr/lib/modules", krel, MOD_SUBDIR)


def builtin(name: str | None, krel: str, root: str = "/") -> bool:
    if not name:
        return False
    try:
        with open(os.path.join(root, "usr/lib/modules", krel, "modules.builtin")) as f:
            return any(line.strip().endswith("/" + name) for line in f)
    except OSError:
        return False


class Installer:
    """Runs one install or removal at a time in a background thread, with a log
    the UI polls. State (what was installed, for which kernel) lives in
    `state_path` so a SteamOS update can be detected."""

    def __init__(self, state_path: str, work_dir: str, run=None, root: str = "/"):
        self.state_path = state_path
        self.work_dir = work_dir
        self.root = root
        self._run_cmd = run or self._subprocess
        self.lock = threading.Lock()
        self.job: dict | None = None

    # ---------------------------------------------------------------- state
    def state(self) -> dict:
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_state(self, st: dict):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f, indent=2)
        os.replace(tmp, self.state_path)

    def status(self, krel: str | None = None) -> dict:
        """Installed drivers and whether each still exists for the running kernel."""
        krel = krel or platform.release()
        out = {}
        for did, rec in self.state().items():
            present = all(os.path.exists(os.path.join(module_dir(krel, self.root), dest))
                          for _src, dest in DRIVERS.get(did, {}).get("modules", []))
            out[did] = {**rec, "present": present, "stale": not present}
        return {"steamos": is_steamos(self.root), "kernel": krel, "installed": out,
                "job": self.job_view()}

    def job_view(self) -> dict | None:
        j = self.job
        if not j:
            return None
        return {"driver": j["driver"], "action": j["action"], "state": j["state"], "step": j["step"],
                "log": j["log"][-12:], "message": j.get("message")}

    # ---------------------------------------------------------------- jobs
    def start(self, driver_id: str, action: str = "install") -> dict:
        if driver_id not in DRIVERS:
            return {"ok": False, "message": "Unknown driver."}
        with self.lock:
            if self.job and self.job["state"] == "running":
                return {"ok": False, "message": "Another driver job is already running."}
            self.job = {"driver": driver_id, "action": action, "state": "running", "step": "Starting",
                        "log": [], "started": time.time()}
        threading.Thread(target=self._job, args=(driver_id, action), daemon=True).start()
        return {"ok": True, "message": "Started."}

    def _log(self, line: str):
        if self.job is not None:
            self.job["log"].append(line.rstrip()[:300])

    def _step(self, name: str):
        if self.job is not None:
            self.job["step"] = name
        self._log(f"== {name}")

    @staticmethod
    def _subprocess(cmd: list[str], cwd: str | None = None, timeout: int = 900) -> tuple[int, str]:
        env = dict(os.environ, LANG="C", LC_ALL="C", PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def _sh(self, cmd: list[str], cwd: str | None = None, check: bool = True, timeout: int = 900) -> tuple[int, str]:
        self._log("$ " + " ".join(cmd))
        try:
            code, out = self._run_cmd(cmd, cwd=cwd, timeout=timeout)
        except FileNotFoundError:
            code, out = 127, f"{cmd[0]}: not found"
        except subprocess.TimeoutExpired:
            code, out = 124, "timed out"
        for line in out.splitlines()[-6:]:
            self._log("  " + line)
        if check and code != 0:
            raise RuntimeError(f"{' '.join(cmd[:3])} failed ({code})")
        return code, out

    def _job(self, driver_id: str, action: str):
        try:
            msg = self._install(driver_id) if action == "install" else self._remove(driver_id)
            self.job.update(state="done", message=msg, step="Done")
        except Exception as e:  # report every failure in the UI
            self._log(f"Error: {e}")
            self.job.update(state="failed", message=str(e), step="Failed")

    def _readonly_off(self) -> bool:
        """Lift SteamOS's read-only flag; returns whether it was on."""
        code, out = self._sh(["steamos-readonly", "status"], check=False)
        was_on = code == 0 and "enabled" in out
        if was_on:
            self._sh(["steamos-readonly", "disable"])
        return was_on

    def _install(self, driver_id: str) -> str:
        d = DRIVERS[driver_id]
        krel = platform.release()
        if not is_steamos(self.root):
            raise RuntimeError(f"Automatic install is for SteamOS only. Follow {d['repo']} for your distribution.")
        if builtin(d.get("builtin_name"), krel, self.root) and driver_id != "universal-pidff":
            raise RuntimeError(f"Your kernel has {d['builtin_name']} built in, so it can't be replaced.")

        self._step("Finding your kernel package")
        code, owner = self._sh(["pacman", "-Qoq", f"/usr/lib/modules/{krel}/vmlinuz"], check=False)
        if code != 0:
            _c, owner = self._sh(["pacman", "-Qoq", f"/usr/lib/modules/{krel}"])
        pkgs = [x.strip() for x in owner.splitlines() if x.strip() and not x.strip().endswith("-headers")]
        if not pkgs:
            raise RuntimeError("Couldn't tell which package provides your kernel.")
        kpkg = pkgs[0]
        build = os.path.join(self.root, "usr/lib/modules", krel, "build")

        was_ro = self._readonly_off()
        try:
            self._step("Installing build tools and kernel headers")
            self._sh(["pacman-key", "--init"])
            self._sh(["pacman-key", "--populate", "archlinux", "holo"], check=False)
            self._sh(["pacman", "-Sy", "--needed", "--noconfirm", "base-devel", "git", f"{kpkg}-headers"],
                     timeout=1800)
            if not os.path.isdir(build):
                raise RuntimeError(f"Kernel headers for {krel} aren't available from SteamOS's repository.")

            self._step(f"Downloading {d['name']}")
            src = os.path.join(self.work_dir, driver_id)
            shutil.rmtree(src, ignore_errors=True)
            os.makedirs(self.work_dir, exist_ok=True)
            clone = ["git", "clone", "--depth", "1"]
            if d.get("submodules"):
                clone += ["--recurse-submodules", "--shallow-submodules"]
            self._sh(clone + [d["repo"], src], timeout=600)
            _c, full = self._sh(["git", "-C", src, "rev-parse", "HEAD"])
            full = full.strip().splitlines()[-1]
            rev = full[:7]
            if d.get("version_placeholder"):
                for dirpath, _dirs, files in os.walk(src):
                    for fn in files:
                        if fn.endswith(".c") or fn == "dkms.conf":
                            p = os.path.join(dirpath, fn)
                            with open(p) as f:
                                txt = f.read()
                            if d["version_placeholder"] in txt:
                                with open(p, "w") as f:
                                    f.write(txt.replace(d["version_placeholder"], rev))

            self._step(f"Building for kernel {krel}")
            if d.get("make_all"):
                self._sh(["make", "-C", src, f"KDIR={build}", "all"], timeout=1800)
            else:
                self._sh(["make", "-C", build, f"M={src}", "modules"], timeout=1800)

            self._step("Installing")
            dest_dir = module_dir(krel, self.root)
            os.makedirs(dest_dir, exist_ok=True)
            files = []
            for s, dest in d["modules"]:
                shutil.copy2(os.path.join(src, s), os.path.join(dest_dir, dest))
                files.append(os.path.join(dest_dir, dest))
            for s, dest in d.get("rules", []):
                rp = os.path.join(self.root, "etc/udev/rules.d", dest)
                os.makedirs(os.path.dirname(rp), exist_ok=True)
                shutil.copy2(os.path.join(src, s), rp)
                files.append(rp)
            self._sh(["depmod", "-a", krel])
        finally:
            if was_ro:
                self._step("Restoring read-only system")
                self._sh(["steamos-readonly", "enable"], check=False)

        self._step("Loading the driver")
        for m in d["unload"]:
            self._sh(["modprobe", "-r", m], check=False)
        for m in d["load"]:
            self._sh(["modprobe", m], check=False)
        self._sh(["udevadm", "control", "--reload-rules"], check=False)
        self._sh(["udevadm", "trigger"], check=False)

        st = self.state()
        st[driver_id] = {"kernel": krel, "commit": rev, "sha": full, "installed": time.time(), "files": files}
        self._save_state(st)
        shutil.rmtree(src, ignore_errors=True)
        return f"{d['name']} ({rev}) installed for kernel {krel}. Unplug the wheel and plug it back in."

    def _remove(self, driver_id: str) -> str:
        d = DRIVERS[driver_id]
        krel = platform.release()
        st = self.state()
        rec = st.get(driver_id, {})
        was_ro = self._readonly_off() if is_steamos(self.root) else False
        try:
            self._step("Removing files")
            files = rec.get("files") or [os.path.join(module_dir(krel, self.root), dest) for _s, dest in d["modules"]]
            for p in files:
                try:
                    os.remove(p)
                    self._log(f"removed {p}")
                except FileNotFoundError:
                    pass
            self._sh(["depmod", "-a", krel], check=False)
        finally:
            if was_ro:
                self._sh(["steamos-readonly", "enable"], check=False)
        for m in d["unload"]:
            self._sh(["modprobe", "-r", m], check=False)
        for m in d.get("restore", []):
            self._sh(["modprobe", m], check=False)
        self._sh(["udevadm", "control", "--reload-rules"], check=False)
        st.pop(driver_id, None)
        self._save_state(st)
        return f"{d['name']} removed. The kernel's own driver is used again after you replug the wheel."
