"""Per-game graphics tuning."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from pitwall import graphics  # noqa: E402

AC_INI = """[VIDEO]
FULLSCREEN=1
WIDTH=3840
HEIGHT=2160
AASAMPLES=8
ANISOTROPIC=16
SHADOW_MAP_SIZE=4096 ; comment kept

[MIRROR]
HQ=1
SIZE=1024

[CUBEMAP]
FACES_PER_FRAME=6
SIZE=2048
FARPLANE=2400

[EFFECTS]
MOTION_BLUR=6
SMOKE=4
"""


def write_log(folder, fps, n=6000, gpu=50):
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, f"game_{time.time_ns()}.csv")
    with open(p, "w") as f:
        f.write("os,cpu,gpu\nLinux,x,y\nfps,frametime,cpu_load,gpu_load\n")
        for i in range(n):
            ft = 1000.0 / (fps(i) if callable(fps) else fps)
            f.write(f"{1000 / ft:.1f},{ft:.3f},30,{gpu}\n")
    return p


class TestDecisions(unittest.TestCase):
    def test_launch_options_round_trip(self):
        cur = "WINEDLLOVERRIDES=x %command% -foo"
        on = graphics.launch_options(cur, True, 60, "/h/.local/share/pitwall/mangohud/tune/244210")
        self.assertIn("MANGOHUD=1", on)
        self.assertIn("fps_limit=60", on)
        self.assertIn("no_display", on)
        self.assertTrue(graphics.has_launch_options(on))
        self.assertTrue(on.endswith("WINEDLLOVERRIDES=x %command% -foo"))
        self.assertEqual(graphics.launch_options(on, False, 60, "x"), cur)
        self.assertEqual(graphics.launch_options(graphics.launch_options(on, True, 60, "/a/tune/1"), True, 60, "/a/tune/1").count("MANGOHUD="), 1)

    def test_start_levels(self):
        self.assertEqual(graphics.start_tier("ac", "steam_machine"), "max")
        self.assertEqual(graphics.start_tier("acc", "steam_machine"), "balanced")
        self.assertEqual(graphics.start_tier("acc", "steam_deck"), "performance")
        self.assertIn("Mid", graphics.advice("acc", "balanced"))

    def test_decide(self):
        e = {"tier": "high", "too_slow": None}
        slow = {"verdict": "too_slow", "avg_fps": 48, "low1_fps": 40}
        self.assertEqual(graphics.decide(e, slow, 60, 99)[0], "balanced")
        ok = {"verdict": "great", "avg_fps": 60, "low1_fps": 59}
        self.assertEqual(graphics.decide(e, ok, 60, 55)[0], "max")       # GPU idle: climb
        self.assertEqual(graphics.decide(e, ok, 60, 92)[0], "high")      # GPU busy: stay
        # never climb back to a level that was too slow here
        self.assertEqual(graphics.decide({"tier": "balanced", "too_slow": "high"}, ok, 60, 40)[0], "balanced")
        self.assertEqual(graphics.decide({"tier": "performance", "too_slow": "high"}, ok, 60, 40)[0], "balanced")
        st = {"verdict": "stutters", "avg_fps": 60, "low1_fps": 55}
        self.assertEqual(graphics.decide(e, st, 60, 50)[0], "high")       # shader stutter: stay


class TestAssettoCorsa(unittest.TestCase):
    def test_only_existing_keys_and_backup(self):
        prefix = tempfile.mkdtemp()
        path = graphics.ac_video_ini(prefix)
        os.makedirs(os.path.dirname(path))
        open(path, "w").write(AC_INI)
        r = graphics.ac_apply(prefix, "balanced")
        self.assertTrue(r["ok"])
        new = open(path).read()
        self.assertIn("AASAMPLES=2", new)
        self.assertIn("SHADOW_MAP_SIZE=2048 ; comment kept", new)
        self.assertIn("WIDTH=2560", new)
        self.assertIn("HEIGHT=1440", new)
        self.assertIn("MOTION_BLUR=0", new)
        self.assertIn("SMOKE=4", new)                  # not Pitwall's to change
        self.assertNotIn("DOF", new)                   # never added
        self.assertEqual(open(path + ".pitwall-backup").read(), AC_INI)
        graphics.ac_apply(prefix, "max")
        self.assertIn("WIDTH=2560", open(path).read())  # resolution is only ever lowered
        self.assertTrue(graphics.ac_restore(prefix))
        self.assertEqual(open(path).read(), AC_INI)

    def test_missing_file(self):
        self.assertFalse(graphics.ac_apply(tempfile.mkdtemp(), "high")["ok"])


class TestTuner(unittest.TestCase):
    def test_full_loop(self):
        tmp = tempfile.mkdtemp()
        prefix = os.path.join(tmp, "pfx")
        path = graphics.ac_video_ini(prefix)
        os.makedirs(os.path.dirname(path))
        open(path, "w").write(AC_INI)
        base = os.path.join(tmp, "mangohud")
        t = graphics.Tuner(os.path.join(tmp, "graphics.json"), tmp, base, "steam_machine",
                           lambda a, n: {"id": "ac", "name": "Assetto Corsa"}, lambda a: prefix)
        e = t.enroll("244210", "Assetto Corsa")
        self.assertEqual(e["tier"], "max")
        self.assertIn("AASAMPLES=4", open(path).read())
        # a session that was too slow
        t.started("244210")
        write_log(graphics.log_dir(base, "244210"), 45, gpu=99)
        r = t.finished("244210", 60)
        self.assertTrue(r["changed"])
        self.assertEqual(r["tier"], "high")
        self.assertIn("lowered to High", r["message"])
        self.assertIn("SHADOW_MAP_SIZE=2048", open(path).read())
        # then smooth with an idle GPU: stays, because Max was too slow here
        t.started("244210")
        write_log(graphics.log_dir(base, "244210"), 60, gpu=40)
        r = t.finished("244210", 60)
        self.assertFalse(r["changed"])
        # state survives a restart
        t2 = graphics.Tuner(os.path.join(tmp, "graphics.json"), tmp, base, "steam_machine",
                            lambda a, n: None, lambda a: prefix)
        st = t2.status()[0]
        self.assertEqual((st["label"], st["auto_settings"]), ("High", True))
        self.assertEqual(st["last"]["verdict"], "great")
        # no log (game closed straight away): nothing changes, no message
        t2.started("244210")
        self.assertIsNone(t2.finished("244210", 60)["message"])
        self.assertTrue(t2.forget("244210"))
        self.assertEqual(open(path).read(), AC_INI)

    def test_guided_game(self):
        tmp = tempfile.mkdtemp()
        t = graphics.Tuner(os.path.join(tmp, "g.json"), tmp, tmp, "steam_machine",
                           lambda a, n: {"id": "acc", "name": "Assetto Corsa Competizione"}, lambda a: None)
        t.enroll("805550", "")
        st = t.status()[0]
        self.assertFalse(st["auto_settings"])
        self.assertIn("Mid preset", st["advice"])
        self.assertIsNone(st["write_error"])


if __name__ == "__main__":
    unittest.main()
