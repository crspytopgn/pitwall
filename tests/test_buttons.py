"""Wheel buttons: reading presses, Steam navigation and in-game layouts."""
import json
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from pitwall import buttons, gamebinds, vpad  # noqa: E402

EV = struct.Struct("<qqHHi")
DEV = {"event": "event5", "id": "346e:0005", "name": "MOZA R3 Base",
       "buttons": [0x120 + i for i in range(12)], "hats": [0]}
DEVS = {DEV["id"]: DEV}


def ev(typ, code, value):
    return EV.pack(0, 0, typ, code, value)


class TestReading(unittest.TestCase):
    def test_bits_and_order(self):
        self.assertEqual(buttons.parse_bits("3 1"), {0, 64, 65})
        # SDL order: BTN_JOYSTICK.. first, then BTN_MISC..
        self.assertEqual(buttons.button_order({0x100, 0x2c0, 0x120}), [0x120, 0x2c0, 0x100])
        self.assertEqual(buttons.hats({0x10, 0x11, 0x12}), [0, 1])

    def test_presses_hats_and_learning(self):
        w = buttons.ButtonWatcher(lambda: [])
        w.devices = DEVS
        seen = []
        w.listeners.append(lambda c, p, d: seen.append((c, p)))
        w.learn(5)
        self.assertEqual(w.learned()["state"], "waiting")
        w.handle(DEV, ev(1, 0x121, 1) + ev(1, 0x121, 0) + ev(1, 0x121, 2))   # repeat ignored
        self.assertEqual(seen, [("346e:0005/b289", True), ("346e:0005/b289", False)])
        r = w.learned()
        self.assertEqual((r["state"], r["label"]), ("done", "Button 2"))
        seen.clear()
        w.handle(DEV, ev(3, 0x11, -1) + ev(3, 0x11, 1) + ev(3, 0x11, 0))
        self.assertEqual(seen, [("346e:0005/hat0-up", True), ("346e:0005/hat0-up", False),
                                ("346e:0005/hat0-down", True), ("346e:0005/hat0-down", False)])
        self.assertEqual(buttons.control_label("346e:0005/hat0-left", DEVS), "D-pad left")

    def test_device_info_from_sysfs(self):
        root = tempfile.mkdtemp()
        base = os.path.join(root, "sys/class/input/event5/device")
        os.makedirs(os.path.join(base, "id"))
        os.makedirs(os.path.join(base, "capabilities"))
        for k, v in {"id/vendor": "346e", "id/product": "0005", "name": "MOZA R3 Base",
                     "capabilities/key": "3 0 0 0 0", "capabilities/abs": "30003"}.items():
            open(os.path.join(base, k), "w").write(v + "\n")
        info = buttons.device_info("event5", root)
        self.assertEqual(info["id"], "346e:0005")
        self.assertEqual(len(info["buttons"]), 2)
        self.assertEqual(info["hats"], [0])


class FakeUinput:
    def __init__(self):
        self.ioctls, self.events = [], []

    def open(self, _p):
        return 99

    def ioctl(self, fd, req, arg=0):
        self.ioctls.append(req)

    def write(self, fd, data):
        self.events.append(EV.unpack(data)[2:])


class TestNavigation(unittest.TestCase):
    def pad(self):
        self.fake = FakeUinput()
        return vpad.VirtualPad(opener=self.fake.open, ioctl=self.fake.ioctl, write=self.fake.write)

    def test_default_map(self):
        m = vpad.default_map(DEV)
        self.assertEqual(m["up"], "346e:0005/hat0-up")
        self.assertEqual(m["a"], "346e:0005/b288")
        self.assertEqual(m["b"], "346e:0005/b289")

    def test_bridge_only_outside_games(self):
        nav = vpad.NavBridge(pad_factory=self.pad)
        nav.configure(True, vpad.default_map(DEV))
        self.assertTrue(nav.active)
        self.assertIn(vpad.UI_DEV_CREATE, self.fake.ioctls)
        nav.on_button("346e:0005/b288", True)
        self.assertIn((1, 0x130, 1), self.fake.events)
        nav.on_button("346e:0005/hat0-down", True)
        self.assertIn((3, vpad.ABS_HAT0Y, 1), self.fake.events)
        nav.set_in_game(True)              # a game owns the wheel now
        self.assertFalse(nav.active)
        self.assertIn((1, 0x130, 0), self.fake.events)    # held buttons released first
        nav.set_in_game(False)
        self.assertTrue(nav.active)
        nav.close()
        self.assertFalse(nav.active)

    def test_quick_access_chord(self):
        p = self.pad()
        p.create()
        p.action("qam", True)
        p.action("qam", False)
        keys = [e for e in self.fake.events if e[0] == 1]
        self.assertEqual(keys, [(1, 0x13C, 1), (1, 0x130, 1), (1, 0x130, 0), (1, 0x13C, 0)])

    def test_missing_uinput_reported(self):
        def broken(_self):
            raise OSError(2, "No such file or directory")
        nav = vpad.NavBridge(pad_factory=lambda: type("P", (), {"create": broken})())
        nav.configure(True, {"a": "x/b1"})
        self.assertFalse(nav.active)
        self.assertIn("virtual controller", nav.error)


class TestGameLayout(unittest.TestCase):
    def test_auto_layout_keeps_your_choices(self):
        lay = gamebinds.auto_layout(DEVS, {"shift_up": "346e:0005/b293"})
        self.assertEqual(lay["shift_up"], "346e:0005/b293")
        self.assertNotIn("shift_down", lay)            # paddles are never guessed
        self.assertEqual(lay["handbrake"], "346e:0005/b288")
        self.assertEqual(len(set(lay.values())), len(lay))
        self.assertEqual(gamebinds.action_for(lay, "346e:0005/b288"), "Handbrake")

    def test_filename(self):
        self.assertEqual(gamebinds.beamng_filename("046d:c262"), "c262046d.diff")
        self.assertEqual(gamebinds.beamng_filename("346e:0005"), "0005346e.diff")

    def test_beamng_write_merge_remove(self):
        home = tempfile.mkdtemp()
        os.environ.pop("XDG_DATA_HOME", None)
        native = os.path.join(home, ".local/share/BeamNG/BeamNG.drive/current")
        maps = os.path.join(native, "settings/inputmaps")
        os.makedirs(maps)
        path = os.path.join(maps, "0005346e.diff")
        mine = {"version": 1, "bindings": [{"control": "button0", "action": "horn"}],
                "removed": [{"control": "button2", "action": "look_back"}]}
        json.dump(mine, open(path, "w"))
        self.assertEqual(gamebinds.beamng_user_folders(home, steam_roots=[]), [native])
        lay = gamebinds.auto_layout(DEVS, {"shift_up": "346e:0005/b293", "shift_down": "346e:0005/b292"})
        r = gamebinds.beamng_apply(home, lay, DEVS, steam_roots=[])
        self.assertTrue(r["ok"])
        data = json.load(open(path))
        b = {(x["control"], x["action"]) for x in data["bindings"]}
        self.assertIn(("button0", "horn"), b)              # yours stays
        self.assertNotIn(("button0", "parkingbrake"), b)   # button taken by you
        self.assertIn(("button5", "shiftUp"), b)
        self.assertIn(("button4", "shiftDown"), b)
        self.assertNotIn(("button2", "look_back"), b)      # you removed that one
        self.assertNotIn("pitwall", json.dumps(data))      # file stays in BeamNG's own format
        # applying again is stable
        gamebinds.beamng_apply(home, lay, DEVS, steam_roots=[])
        self.assertEqual(json.load(open(path))["bindings"], data["bindings"])
        self.assertTrue(gamebinds.beamng_status(home, steam_roots=[])["applied"])
        gamebinds.beamng_remove(home, steam_roots=[])
        self.assertEqual(json.load(open(path))["bindings"], mine["bindings"])
        self.assertFalse(gamebinds.beamng_status(home, steam_roots=[])["applied"])

    def test_beamng_not_installed(self):
        r = gamebinds.beamng_apply(tempfile.mkdtemp(), {"horn": "346e:0005/b288"}, DEVS, steam_roots=[])
        self.assertFalse(r["ok"])
        self.assertIn("Start BeamNG once", r["error"])


if __name__ == "__main__":
    unittest.main()
