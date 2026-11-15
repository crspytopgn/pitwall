"""BeamNG.drive: its own wheel profiles, Pitwall's button layout and graphics."""
import json
import os
import sys
import tempfile
import unittest
import xml.dom.minidom
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from pitwall import buttons, compat, gamebinds, gamesettings as gs, graphics  # noqa: E402

R3 = {"id": "346e:0005", "name": "Gudsen MOZA R3 Base", "buttons": [0x120 + i for i in range(30)], "hats": [0]}
DEVS = {R3["id"]: R3}
FACTORY = {"bindings": [{"control": "button12", "action": "shiftUp"}, {"control": "button13", "action": "shiftDown"},
                        {"control": "button3", "action": "parkingbrake"}, {"control": "xaxis", "action": "steering"}]}


def library(home, inputmap=None, zipped=False):
    root = os.path.join(home, ".local/share/Steam")
    os.makedirs(os.path.join(root, "steamapps"), exist_ok=True)
    open(os.path.join(root, "steamapps", "libraryfolders.vdf"), "w").write('"libraryfolders" {}')
    inst = os.path.join(root, "steamapps/common/BeamNG.drive")
    os.makedirs(inst, exist_ok=True)
    if inputmap is not None:
        if zipped:
            with zipfile.ZipFile(os.path.join(inst, "content.zip"), "w") as z:
                z.writestr("settings/inputmaps/0005346e.json", json.dumps(inputmap))
        else:
            os.makedirs(os.path.join(inst, "settings/inputmaps"))
            json.dump(inputmap, open(os.path.join(inst, "settings/inputmaps/0005346e.json"), "w"))
    return root


class TestFactoryProfile(unittest.TestCase):
    def test_read_loose_and_zipped(self):
        for zipped in (False, True):
            home = tempfile.mkdtemp()
            library(home, FACTORY, zipped)
            fac = gamebinds.beamng_factory(home, R3["id"])
            self.assertEqual(len(fac), 4, zipped)
        self.assertEqual(gamebinds.beamng_factory(tempfile.mkdtemp(), R3["id"]), [])

    def test_r3_paddles_known_for_every_game(self):
        fac = {R3["id"]: FACTORY["bindings"]}
        for game in ("beamng", "acc", "f1_24", "ets2"):
            lay = gamebinds.auto_layout(DEVS, {}, game, factory=fac)
            self.assertEqual(lay["shift_up"], "346e:0005/b%d" % (0x120 + 12), game)
            self.assertEqual(lay["shift_down"], "346e:0005/b%d" % (0x120 + 13), game)
            others = [c for a, c in lay.items() if a not in ("shift_up", "shift_down")]
            self.assertNotIn(lay["shift_up"], others)

    def test_beamng_keeps_its_own_profile(self):
        fac = {R3["id"]: FACTORY["bindings"]}
        lay = gamebinds.auto_layout(DEVS, {}, "beamng", factory=fac)
        self.assertEqual(lay["handbrake"], "346e:0005/b%d" % (0x120 + 3))       # BeamNG's own choice
        self.assertTrue(gamebinds.is_factory("handbrake", lay["handbrake"], DEVS, fac))
        diffs = gamebinds.beamng_diffs(lay, DEVS, fac)["0005346e.diff"]
        controls = {d["control"] for d in diffs}
        actions = {d["action"] for d in diffs}
        self.assertNotIn("button3", controls)          # already bound by BeamNG
        self.assertNotIn("button12", controls)
        self.assertNotIn("parkingbrake", actions)
        self.assertIn("look_back", actions)            # the buttons BeamNG leaves empty get jobs
        self.assertGreaterEqual(len(diffs), 8)


class TestFolders(unittest.TestCase):
    def test_every_linux_setup(self):
        home = tempfile.mkdtemp()
        os.environ.pop("XDG_DATA_HOME", None)
        native = os.path.join(home, ".local/share/BeamNG/BeamNG.drive/current")
        flat = os.path.join(home, ".var/app/com.valvesoftware.Steam/.local/share/BeamNG/BeamNG.drive/current")
        root = library(home)
        proton = os.path.join(root, "steamapps/compatdata/284160/pfx/drive_c/users/steamuser/AppData/Local/BeamNG.drive/latest")
        old = os.path.join(root, "steamapps/compatdata/284160/pfx/drive_c/users/steamuser/AppData/Local/BeamNG.Drive/0.9")
        newer = os.path.join(os.path.dirname(old), "0.36")
        for d in (native, flat, proton, old, newer):
            os.makedirs(d)
        found = gamebinds.beamng_user_folders(home)
        for d in (native, flat, proton, newer):
            self.assertIn(d, found)
        self.assertNotIn(old, found)                   # 0.36 is newer than 0.9

    def test_flatpak_steam_library(self):
        home = tempfile.mkdtemp()
        base = os.path.join(home, ".var/app/com.valvesoftware.Steam/.local/share/Steam")
        os.makedirs(os.path.join(base, "steamapps"))
        open(os.path.join(base, "steamapps/libraryfolders.vdf"), "w").write("{}")
        self.assertIn(os.path.realpath(base), compat.steam_roots(home))


class TestGraphics(unittest.TestCase):
    SETTINGS = {"GraphicAnisotropic": 16, "GraphicDisplayResolutions": "3840 2160", "GraphicDynReflectionEnabled": True,
                "GraphicGrassDensity": 1, "GraphicLightingQuality": "Ultra", "GraphicMeshQuality": "Ultra",
                "GraphicOverallQuality": "High", "GraphicShadowsQuality": "Ultra", "GraphicTextureQuality": "High",
                "PostFXMotionBlurEnabled": True, "SomethingElse": "kept"}

    def test_levels(self):
        base = json.dumps(self.SETTINGS)
        perf = json.loads(gs.beamng(base, base, "performance")[0])
        self.assertEqual(perf["GraphicMeshQuality"], "Low")
        self.assertEqual(perf["GraphicLightingQuality"], "Lowest")
        self.assertEqual(perf["GraphicTextureQuality"], "Normal")           # textures drop more slowly
        self.assertFalse(perf["GraphicDynReflectionEnabled"])
        self.assertEqual(perf["GraphicDisplayResolutions"], "1920 1080")
        self.assertEqual(perf["GraphicOverallQuality"], "Custom")
        self.assertEqual(perf["SomethingElse"], "kept")
        self.assertNotIn("GraphicTerrainQuality", perf)                    # never added
        back = json.loads(gs.beamng(json.dumps(perf), base, "max")[0])
        self.assertEqual(back, self.SETTINGS)
        self.assertEqual(gs.beamng("not json", "not json", "high"), ("not json", []))

    def test_tuner_finds_and_writes_it(self):
        home = tempfile.mkdtemp()
        os.environ.pop("XDG_DATA_HOME", None)
        folder = os.path.join(home, ".local/share/BeamNG/BeamNG.drive/current/settings")
        os.makedirs(folder)
        path = os.path.join(folder, "settings.json")
        json.dump(self.SETTINGS, open(path, "w"))
        t = graphics.Tuner(os.path.join(home, "g.json"), home, home, "steam_machine",
                           lambda a, n: {"id": "beamng", "name": "BeamNG.drive"}, lambda a: None)
        t.enroll("284160", "BeamNG.drive")
        self.assertEqual(json.load(open(path))["GraphicMeshQuality"], "Normal")   # heavy game: Balanced
        st = t.status()[0]
        self.assertTrue(st["auto_settings"])
        self.assertIn("settings.json", st["advice"])
        t.forget("284160")
        self.assertEqual(json.load(open(path)), self.SETTINGS)


class TestDiagram(unittest.TestCase):
    def test_svg_is_valid_and_lists_the_layout(self):
        fac = {R3["id"]: FACTORY["bindings"]}
        lay = gamebinds.auto_layout(DEVS, {}, "acc", factory=fac)
        svg = gamebinds.diagram_svg(lay, DEVS, "acc", fac)
        xml.dom.minidom.parseString(svg)
        self.assertIn("Pit limiter", svg)
        self.assertIn("Shift up", svg)
        self.assertIn("on-screen display", svg)
        empty = gamebinds.diagram_svg({}, {}, "acc")
        xml.dom.minidom.parseString(empty)
        self.assertIn("not set", empty)
        xml.dom.minidom.parseString(gamebinds.diagram_svg(lay, DEVS, "<&>\"'", fac))


if __name__ == "__main__":
    unittest.main()
