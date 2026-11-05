"""Loads main.py with a stub `decky` module and exercises the Decky-facing API."""

import asyncio
import logging
import os
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPluginBackend(unittest.TestCase):
    def test_lifecycle_and_calls(self):
        tmp = tempfile.mkdtemp()
        d = types.ModuleType("decky")
        d.DECKY_PLUGIN_SETTINGS_DIR = os.path.join(tmp, "settings")
        d.DECKY_PLUGIN_RUNTIME_DIR = os.path.join(tmp, "data")
        d.DECKY_USER_HOME = os.path.join(tmp, "home")
        d.DECKY_USER = "nobody"
        d.logger = logging.getLogger("pitwall-test")
        sys.modules["decky"] = d
        sys.path.insert(0, ROOT)
        os.environ["PITWALL_MOZA_TTY"] = "/nonexistent"
        import importlib
        main = importlib.import_module("main")
        main.Plugin.__init__ = lambda self: None

        async def go():
            p = main.Plugin()
            # use free ports so tests don't clash with a real Pitwall
            main.DEFAULTS["dashboard_port"] = 48191
            main.DEFAULTS["ports"] = {"outgauge": 48444, "motionsim": 48445, "forza": 48300, "codemasters": 48777}
            await p._main()
            ws = await p.wheel_status()
            self.assertIn("connected", ws)
            st = await p.session_status()
            self.assertFalse(st["receiving"])
            self.assertTrue(len(await p.compat_list()) > 10)
            r = await p.game_changed("266410", "iRacing", True)
            self.assertEqual(r["game"]["status"], "broken")
            checks = await p.health_check()
            self.assertTrue(any(c["id"] == "compat" for c in checks))
            self.assertIn("%command%", await p.benchmark_options(60))
            self.assertFalse((await p.perf_analyse("", ""))["ok"])
            self.assertEqual((await p.debrief())["lines"], ["No laps recorded this session yet."])
            self.assertTrue(await p.set_setting("anthropic_api_key", "sk-test"))
            self.assertIs((await p.get_settings())["anthropic_api_key"], True)   # key never returned
            self.assertFalse(await p.set_setting("ports", {}))
            cat = await p.ffb_catalogue()
            self.assertEqual(len(cat["presets"]), 3)
            self.assertFalse((await p.ffb_nudge("too_light"))["ok"])       # no wheel connected
            self.assertFalse((await p.ffb_undo())["ok"])
            bs = await p.bridge_status("805550")
            self.assertTrue(bs["supported"])
            self.assertFalse(bs["installed"])
            self.assertIn("winecarte-run", await p.bridge_launch_options("", True))
            self.assertFalse((await p.bridge_status("284160"))["supported"])
            self.assertTrue(await p.set_setting("rev_lights", True))
            self.assertIsNotNone(p.rev_lights)
            self.assertTrue(await p.set_setting("rev_lights", False))
            self.assertIsNone(p.rev_lights)
            await p._unload()
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
