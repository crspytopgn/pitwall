import os
import platform
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from pitwall import drivers, ffbtest  # noqa: E402


class TestFfbTest(unittest.TestCase):
    def test_effect_layout(self):
        # Offsets checked with gcc against <linux/input.h>: 48 bytes, union at 16.
        b = ffbtest.pack_constant(0x1000, ffbtest.LEFT, 600)
        self.assertEqual(len(b), 48)
        typ, eid, direction = struct.unpack_from("<HhH", b, 0)
        self.assertEqual((typ, eid, direction), (0x52, -1, 0x4000))
        self.assertEqual(struct.unpack_from("<HH", b, 10), (600, 0))          # replay length, delay
        self.assertEqual(struct.unpack_from("<hHHHH", b, 16), (0x1000, 150, 0, 150, 0))
        self.assertEqual(len(ffbtest.input_event(0x15, 3, 1)), 24)

    def test_caps(self):
        # MOZA-style: constant, spring, friction, damper, inertia, ramp, periodic waveforms, gain
        def words(*codes):
            m = sum(1 << c for c in codes)
            return f"{m >> 64:x} {m & (2**64 - 1):x}"
        caps = ffbtest.parse_caps(words(0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x5a, 0x60))
        for e in ("constant", "spring", "friction", "damper", "periodic", "gain"):
            self.assertIn(e, caps)
        self.assertEqual(ffbtest.caps_summary(caps)["verdict"], "full")
        # Stock Logitech driver: constant and autocentre only
        only_const = ffbtest.parse_caps(words(0x52, 0x61))
        self.assertEqual(only_const, ["constant", "autocentre"])
        s = ffbtest.caps_summary(only_const)
        self.assertEqual(s["verdict"], "partial")
        self.assertIn("spring", s["missing"])
        self.assertEqual(ffbtest.caps_summary([])["verdict"], "none")

    def test_run_test_plays_left_then_right(self):
        calls = []

        def fake_ioctl(fd, req, buf, mutate=False):
            calls.append(req)
            if req == ffbtest.EVIOCSFF:
                struct.pack_into("<h", buf, 2, 7)       # kernel assigns an id

        with tempfile.NamedTemporaryFile() as f:
            r = ffbtest.run_test(f.name, strength=0.9, ioctl=fake_ioctl, sleep=lambda s: None)
            data = open(f.name, "rb").read()
        self.assertTrue(r["ok"])
        self.assertEqual(calls, [ffbtest.EVIOCSFF, ffbtest.EVIOCRMFF] * 2)
        events = [struct.unpack_from("<qqHHi", data, i)[2:] for i in range(0, len(data), 24)]
        self.assertEqual(events, [(0x15, 0x60, 0xFFFF), (0x15, 7, 1), (0x15, 7, 0), (0x15, 7, 1), (0x15, 7, 0)])

    def test_strength_is_capped(self):
        levels = []

        def fake_ioctl(fd, req, buf, mutate=False):
            if req == ffbtest.EVIOCSFF:
                levels.append(struct.unpack_from("<h", buf, 16)[0])
                struct.pack_into("<h", buf, 2, 0)

        with tempfile.NamedTemporaryFile() as f:
            ffbtest.run_test(f.name, strength=1.0, ioctl=fake_ioctl, sleep=lambda s: None)
        self.assertEqual(levels, [int(0x7FFF * 0.4)] * 2)


class TestDriverChoice(unittest.TestCase):
    def test_driver_for(self):
        up = {"driver": "hid-universal-pidff (in Linux 6.15+)", "driver_url": None}
        self.assertEqual(drivers.driver_for(up, has_universal_pidff=False), "universal-pidff")
        self.assertIsNone(drivers.driver_for(up, has_universal_pidff=True))
        self.assertEqual(drivers.driver_for({"driver": "hid-logitech", "driver_url": "https://github.com/berarma/new-lg4ff"}, True), "new-lg4ff")
        self.assertEqual(drivers.driver_for({"driver": "hid-fanatecff"}, True), "hid-fanatecff")
        self.assertEqual(drivers.driver_for({"driver": "hid-tmff2"}, True), "hid-tmff2")
        self.assertEqual(drivers.driver_for({"driver": "simagic-ff"}, True), "simagic-ff")
        self.assertIsNone(drivers.driver_for({"driver": "hid-pidff (full support in Linux 6.15+)"}, False))
        self.assertIsNone(drivers.driver_for(None, False))


class FakeSteamOS:
    """Records commands and imitates their effects in a temporary root."""

    def __init__(self, root, readonly=True, fail=None):
        self.root, self.readonly, self.fail, self.cmds = root, readonly, fail, []
        self.krel = platform.release()

    def __call__(self, cmd, cwd=None, timeout=0):
        self.cmds.append(cmd)
        c = cmd[0]
        if self.fail and self.fail in " ".join(cmd):
            return 1, "error: simulated failure"
        if cmd[:2] == ["steamos-readonly", "status"]:
            return 0, "enabled" if self.readonly else "disabled"
        if cmd[:2] == ["steamos-readonly", "disable"]:
            self.readonly = False
        if cmd[:2] == ["steamos-readonly", "enable"]:
            self.readonly = True
        if c == "pacman" and cmd[1] == "-Qoq":
            return 0, "linux-neptune-616\n"
        if c == "pacman" and cmd[1] == "-Sy":
            assert not self.readonly, "pacman ran with the system read-only"
            os.makedirs(os.path.join(self.root, "usr/lib/modules", self.krel, "build"), exist_ok=True)
        if c == "git" and cmd[1] == "clone":
            dest = cmd[-1]
            os.makedirs(os.path.join(dest, "deps/hid-tminit"), exist_ok=True)
            os.makedirs(os.path.join(dest, "udev"), exist_ok=True)
            with open(os.path.join(dest, "hid-ftec.c"), "w") as f:
                f.write('MODULE_VERSION("#VERSION#");')
            for r in ("fanatec.rules", "udev/71-thrustmaster-steamdeck.rules"):
                open(os.path.join(dest, r), "w").close()
        if c == "git" and cmd[1] == "-C":
            return 0, "abc1234" + "0" * 33 + "\n"
        if c == "make":
            src = cmd[2] if cmd[1] == "-C" and "KDIR=" in cmd[3] else cmd[3][2:]
            for d in drivers.DRIVERS.values():
                for s, _dest in d["modules"]:
                    p = os.path.join(src, s)
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    open(p, "w").close()
            self.built_src = src
        return 0, ""


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "etc"))
        with open(os.path.join(self.root, "etc/os-release"), "w") as f:
            f.write('NAME="SteamOS"\nID=steamos\n')
        self.state = os.path.join(self.root, "drivers.json")
        self.work = os.path.join(self.root, "work")

    def tearDown(self):
        self.tmp.cleanup()

    def run_job(self, inst, did, action="install"):
        self.assertTrue(inst.start(did, action)["ok"])
        for _ in range(200):
            if inst.job["state"] != "running":
                break
            time.sleep(0.01)
        return inst.job

    def test_install_universal_pidff(self):
        fake = FakeSteamOS(self.root)
        inst = drivers.Installer(self.state, self.work, run=fake, root=self.root)
        job = self.run_job(inst, "universal-pidff")
        self.assertEqual(job["state"], "done", job["log"])
        flat = [" ".join(c) for c in fake.cmds]
        self.assertIn("steamos-readonly disable", flat)
        self.assertEqual(flat[-1], "udevadm trigger")
        self.assertTrue(fake.readonly, "read-only flag restored")
        self.assertIn("pacman -Sy --needed --noconfirm base-devel git linux-neptune-616-headers", flat)
        ko = os.path.join(drivers.module_dir(fake.krel, self.root), "hid_universal_pidff.ko")
        self.assertTrue(os.path.exists(ko))
        st = inst.status(fake.krel)
        self.assertTrue(st["installed"]["universal-pidff"]["present"])
        self.assertEqual(st["installed"]["universal-pidff"]["commit"], "abc1234")
        # After a SteamOS update to a new kernel, it's reported as needing a reinstall.
        self.assertTrue(inst.status("6.99.0-valve1")["installed"]["universal-pidff"]["stale"])

    def test_logitech_replaces_in_kernel_module(self):
        fake = FakeSteamOS(self.root)
        inst = drivers.Installer(self.state, self.work, run=fake, root=self.root)
        self.assertEqual(self.run_job(inst, "new-lg4ff")["state"], "done")
        self.assertTrue(os.path.exists(os.path.join(drivers.module_dir(fake.krel, self.root), "hid-logitech.ko")))
        flat = [" ".join(c) for c in fake.cmds]
        self.assertLess(flat.index("modprobe -r hid_logitech"), flat.index("modprobe hid-logitech"))
        # Removing it brings back the stock driver.
        fake.cmds.clear()
        self.assertEqual(self.run_job(inst, "new-lg4ff", "remove")["state"], "done")
        self.assertFalse(os.path.exists(os.path.join(drivers.module_dir(fake.krel, self.root), "hid-logitech.ko")))
        self.assertIn(["modprobe", "hid-logitech"], fake.cmds)
        self.assertNotIn("new-lg4ff", inst.state())

    def test_fanatec_rules_and_version(self):
        fake = FakeSteamOS(self.root)
        inst = drivers.Installer(self.state, self.work, run=fake, root=self.root)
        self.assertEqual(self.run_job(inst, "hid-fanatecff")["state"], "done")
        self.assertTrue(os.path.exists(os.path.join(self.root, "etc/udev/rules.d/99-fanatec.rules")))

    def test_tmff2_builds_with_submodules(self):
        fake = FakeSteamOS(self.root)
        inst = drivers.Installer(self.state, self.work, run=fake, root=self.root)
        self.assertEqual(self.run_job(inst, "hid-tmff2")["state"], "done")
        clone = next(c for c in fake.cmds if c[:2] == ["git", "clone"])
        self.assertIn("--recurse-submodules", clone)
        d = drivers.module_dir(fake.krel, self.root)
        self.assertTrue(os.path.exists(os.path.join(d, "hid-tmff-new.ko")))
        self.assertTrue(os.path.exists(os.path.join(d, "hid-tminit.ko")))

    def test_failure_restores_readonly_and_reports(self):
        fake = FakeSteamOS(self.root, fail="make")
        inst = drivers.Installer(self.state, self.work, run=fake, root=self.root)
        job = self.run_job(inst, "universal-pidff")
        self.assertEqual(job["state"], "failed")
        self.assertTrue(fake.readonly, "read-only flag restored after a failure")
        self.assertNotIn("universal-pidff", inst.state())

    def test_not_steamos(self):
        os.remove(os.path.join(self.root, "etc/os-release"))
        fake = FakeSteamOS(self.root)
        inst = drivers.Installer(self.state, self.work, run=fake, root=self.root)
        job = self.run_job(inst, "universal-pidff")
        self.assertEqual(job["state"], "failed")
        self.assertIn("SteamOS only", job["message"])
        self.assertEqual(fake.cmds, [])

    def test_one_job_at_a_time(self):
        inst = drivers.Installer(self.state, self.work, run=FakeSteamOS(self.root), root=self.root)
        inst.job = {"state": "running"}
        self.assertFalse(inst.start("universal-pidff")["ok"])
        self.assertFalse(inst.start("nope")["ok"])


if __name__ == "__main__":
    unittest.main()


class TestUninstall(unittest.TestCase):
    def test_remove_all_and_hwdb(self):
        from pitwall import health
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "etc"))
            with open(os.path.join(root, "etc/os-release"), "w") as f:
                f.write("ID=steamos\n")
            fake = FakeSteamOS(root)
            inst = drivers.Installer(os.path.join(root, "d.json"), os.path.join(root, "w"), run=fake, root=root)
            for did in ("universal-pidff", "hid-fanatecff"):
                inst.start(did)
                for _ in range(200):
                    if inst.job["state"] != "running":
                        break
                    time.sleep(0.01)
            self.assertEqual(sorted(inst.state()), ["hid-fanatecff", "universal-pidff"])
            self.assertEqual(sorted(inst.remove_all()), ["hid-fanatecff", "universal-pidff"])
            self.assertEqual(inst.state(), {})
            self.assertFalse(os.listdir(drivers.module_dir(fake.krel, root)))
            self.assertFalse(os.path.exists(os.path.join(root, "etc/udev/rules.d/99-fanatec.rules")))
            self.assertTrue(fake.readonly)
            hw = os.path.join(root, "hw.hwdb")
            open(hw, "w").close()
            self.assertTrue(health.remove_joystick_fix(hw, run=lambda c: None))
            self.assertFalse(os.path.exists(hw))
            self.assertFalse(health.remove_joystick_fix(hw, run=lambda c: None))
