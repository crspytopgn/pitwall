"""Game settings files, by engine format."""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from pitwall import gamesettings as gs, graphics  # noqa: E402

UE = """[ScalabilityGroups]
sg.ResolutionQuality=100.000000
sg.ViewDistanceQuality=3
sg.AntiAliasingQuality=3
sg.ShadowQuality=3
sg.PostProcessQuality=3
sg.TextureQuality=3
sg.EffectsQuality=3
sg.FoliageQuality=3
sg.ShadingQuality=3

[/Script/Engine.GameUserSettings]
ResolutionSizeX=3840
"""

EGO = """<?xml version="1.0" encoding="UTF-8" ?>
<hardware_settings_config applyOOTB="false">
	<graphics_card>
		<resolution width="3840" height="2160" displayMode="0" vsync="false">
			<refreshRate numerator="0" denominator="0" />
		</resolution>
	</graphics_card>
	<rt_quality quality="3" />
	<rt_shadows enabled="true" />
	<rt_reflections enabled="true" />
	<rt_ao enabled="false" />
</hardware_settings_config>
"""

MADNESS = """<?xml version="1.0"?>
<Reflection>
<data class="GraphicConfigData" id="0x423F0500">
<prop name="Mode" adapter="0" width="3840" height="2160" refresh_num="60000" refresh_dem="1000" />
<prop name="AntiAlias" antialias="2" />
<prop name="CarDetailLevel" cardetaillevel="3" />
<prop name="TrackDetailLevel" trackdetaillevel="3" />
<prop name="ShadowDetailLevel" shadowdetaillevel="1" />
<prop name="MotionblurLevel" motionblurlevel="2" />
<prop name="EnvmapReflectionDetailLevel" envmapreflectiondetaillevel="3" />
<prop name="SuperSampling" supersampling="1" />
</data>
</Reflection>
"""

SCS = """uset r_scale_x "1.0"
uset r_scale_y "1.0"
uset r_sun_shadow_quality "4"
uset r_sun_shadow_texture_size "4096"
uset r_mirror_view_distance "200"
uset r_ssao "1"
uset r_dof "1"
uset r_msaa "4"
"""


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class TestFormats(unittest.TestCase):
    def test_unreal(self):
        new, ch = gs.unreal(UE, UE, "balanced")
        self.assertIn("sg.ShadowQuality=1", new)
        self.assertIn("sg.TextureQuality=2", new)
        self.assertIn("sg.ResolutionQuality=75.000000", new)
        self.assertNotIn("sg.GlobalIlluminationQuality", new)          # never added
        self.assertIn("ResolutionSizeX=3840", new)                      # not touched
        self.assertEqual(gs.unreal(new, UE, "balanced")[1], [])         # stable
        # render scale is never raised above yours
        low = UE.replace("sg.ResolutionQuality=100.000000", "sg.ResolutionQuality=50.000000")
        self.assertIn("sg.ResolutionQuality=50.000000", gs.unreal(low, low, "max")[0])

    def test_ego(self):
        new, ch = gs.ego(EGO, EGO, "performance")
        self.assertIn('width="1920" height="1080"', new)
        self.assertIn('<rt_shadows enabled="false"', new)
        self.assertIn('<rt_reflections enabled="false"', new)
        self.assertIn('<rt_quality quality="3"', new)                   # left alone
        back, _ = gs.ego(new, EGO, "max")
        self.assertEqual(back, EGO)                                       # Max: your settings again

    def test_madness_relative(self):
        new, ch = gs.madness(MADNESS, MADNESS, "balanced")
        self.assertIn('cardetaillevel="1"', new)
        self.assertIn('shadowdetaillevel="0"', new)                      # never below 0
        self.assertIn('motionblurlevel="0"', new)
        self.assertIn('supersampling="0"', new)
        self.assertIn('width="2560" height="1440"', new)
        self.assertIn('antialias="2"', new)
        self.assertEqual(gs.madness(new, MADNESS, "max")[0], MADNESS)

    def test_scs(self):
        new, ch = gs.scs(SCS, SCS, "performance")
        self.assertIn('uset r_scale_x "0.77"', new)
        self.assertIn('uset r_sun_shadow_quality "1"', new)
        self.assertIn('uset r_sun_shadow_texture_size "1024"', new)
        self.assertIn('uset r_mirror_view_distance "80"', new)
        self.assertIn('uset r_ssao "0"', new)
        self.assertIn('uset r_msaa "4"', new)
        self.assertEqual(gs.scs(new, SCS, "max")[0], SCS)


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.prefix = os.path.join(self.home, "pfx")
        self.u = gs.user_dir(self.prefix)

    def test_find_each_format(self):
        put(os.path.join(self.u, "AppData/Local/WRC/Saved/Config/WindowsNoEditor/GameUserSettings.ini"), UE)
        put(os.path.join(self.u, "AppData/Local/EpicGamesLauncher/Saved/Config/Windows/GameUserSettings.ini"), UE)
        put(os.path.join(self.u, "Documents/My Games/F1 23/hardwaresettings/hardware_settings_config.xml"), EGO)
        put(os.path.join(self.u, "Documents/Automobilista 2/graphicsconfigdx11.xml"), MADNESS)
        put(os.path.join(self.u, "Documents/Euro Truck Simulator 2/config.cfg"), SCS)
        kinds = sorted(k for k, _ in gs.find(self.prefix, self.home))
        self.assertEqual(kinds, ["ego", "madness", "scs", "unreal"])     # the launcher's file is skipped
        native = os.path.join(self.home, ".local/share/American Truck Simulator/config.cfg")
        put(native, SCS)
        self.assertIn(("scs", native), gs.find(None, self.home, "ats"))
        self.assertEqual(gs.find(None, self.home, "acc"), [])

    def test_apply_restore_and_your_changes(self):
        path = os.path.join(self.u, "Documents/Automobilista 2/graphicsconfigdx11.xml")
        put(path, MADNESS)
        r = gs.apply("madness", path, "performance")
        self.assertTrue(r["ok"])
        self.assertIn('cardetaillevel="0"', open(path).read())
        # the game rewrites the file on exit, reformatted but same values: still your old settings
        put(path, open(path).read().replace("\n", "\r\n"))
        gs.apply("madness", path, "high")
        self.assertIn('cardetaillevel="2"', open(path).read())
        # you change a setting Pitwall controls in the game: that becomes your settings
        put(path, open(path).read().replace('trackdetaillevel="2"', 'trackdetaillevel="1"'))
        gs.apply("madness", path, "max")
        self.assertIn('trackdetaillevel="1"', open(path).read())
        self.assertTrue(gs.restore(path))
        self.assertEqual(open(path).read(), MADNESS)
        self.assertFalse(any(os.path.exists(x) for x in gs.sidecars(path)))


class TestRacingOnly(unittest.TestCase):
    def test_only_frames_while_driving_count(self):
        d = tempfile.mkdtemp()
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(1_800_000_000))
        path = os.path.join(d, f"acs_{stamp}.csv")
        with open(path, "w") as f:
            f.write("os,cpu\nLinux,x\nfps,frametime,cpu_load,gpu_load,elapsed\n")
            for i in range(6000):                       # 10 minutes at 100 ms
                slow = i < 3000                          # menus/loading: slow frames
                ft = 50.0 if slow else 16.6
                f.write(f"{1000/ft:.1f},{ft},20,{30 if slow else 60},{i * 100_000_000}\n")
        start = 1_800_000_000
        # telemetry: driving from minute 5 to minute 10
        rows, how = graphics.racing_rows(path, [(start + 300, start + 600)])
        self.assertEqual(how, "telemetry")
        self.assertTrue(all(r[1] == 16.6 for r in rows))
        self.assertGreater(graphics.seconds_of(rows), 280)
        rows, how = graphics.racing_rows(path, [])
        self.assertEqual(how, "time")
        self.assertEqual(len(rows), 6000 - 1200)


class TestTunerWrites(unittest.TestCase):
    def test_waits_for_the_game_to_close(self):
        tmp = tempfile.mkdtemp()
        prefix = os.path.join(tmp, "pfx")
        ini = os.path.join(gs.user_dir(prefix), "AppData/Local/WRC/Saved/Config/WindowsNoEditor/GameUserSettings.ini")
        put(ini, UE)
        t = graphics.Tuner(os.path.join(tmp, "g.json"), tmp, tmp, "steam_machine",
                           lambda a, n: {"id": "eawrc", "name": "EA SPORTS WRC"}, lambda a: prefix)
        e = t.enroll("1849250", "", running=True)
        self.assertTrue(e["pending"])
        self.assertEqual(open(ini).read(), UE)                   # not while the game runs
        t.started("1849250")
        r = t.finished("1849250", 60, [])
        self.assertFalse(r["changed"])                           # no log: nothing judged
        self.assertIn("sg.ShadowQuality=2", open(ini).read())     # but now it's closed, the level is written
        st = t.status()[0]
        self.assertTrue(st["auto_settings"])
        self.assertIn("Unreal Engine", st["advice"])
        self.assertTrue(t.forget("1849250"))
        self.assertEqual(open(ini).read(), UE)


if __name__ == "__main__":
    unittest.main()
