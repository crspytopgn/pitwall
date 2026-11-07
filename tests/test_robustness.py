"""Regression tests from the fuzzing pass: hostile input must never stop
telemetry, and the dashboard must always get valid JSON."""
import asyncio
import json
import math
import os
import random
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from pitwall import dashboard  # noqa: E402
from pitwall.telemetry import parsers  # noqa: E402
from pitwall.telemetry.frame import Frame  # noqa: E402
from pitwall.telemetry.sources import UdpListener  # noqa: E402

NAN, INF = float("nan"), float("inf")


class TestSanitize(unittest.TestCase):
    def test_non_finite_and_ranges(self):
        f = Frame(sim="x", speed=NAN, rpm=INF, max_rpm=NAN, throttle=7.0, brake=-1.0, gear=NAN, pos=(1.0, NAN, 0.0),
                  lap=INF, lap_time=NAN, last_lap=-5.0, best_lap=INF, fuel=2.0, fuel_l=NAN, tyre_temp=[NAN, 80.0, 81.0, 82.0],
                  tyre_window=(70.0, NAN, 100.0), extra={"abs": True, "acc": (NAN, 1.0)}).sanitize()
        self.assertEqual((f.speed, f.rpm, f.max_rpm, f.throttle, f.brake, f.gear), (0.0, 0.0, None, 1.0, 0.0, 0))
        self.assertIsNone(f.pos)
        self.assertIsNone(f.lap)
        self.assertIsNone(f.last_lap)
        self.assertIsNone(f.best_lap)
        self.assertEqual(f.fuel, 1.0)
        self.assertEqual(f.tyre_temp, [None, 80.0, 81.0, 82.0])
        self.assertIsNone(f.tyre_window)
        self.assertIs(f.extra["abs"], True)
        self.assertIsNone(f.extra["acc"])
        json.dumps(f.to_dict(), allow_nan=False)

    def test_normal_frame_unchanged(self):
        f = Frame(sim="ac", speed=50.0, rpm=7000.0, max_rpm=8000.0, throttle=0.5, brake=0.0, gear=4, pos=(1.0, 2.0, 3.0),
                  lap=3, lap_time=12.5, last_lap=101.2, best_lap=100.9, fuel=0.4, tyre_temp=[80.0, 81.0, 82.0, 83.0])
        before = f.to_dict()
        self.assertEqual(f.sanitize().to_dict(), before)

    def test_safe_json(self):
        self.assertEqual(json.loads(dashboard.safe_json({"a": NAN, "b": [1.0, INF], "c": {"d": -INF}})),
                         {"a": None, "b": [1.0, None], "c": {"d": None}})


class TestParsersNeverStopTelemetry(unittest.TestCase):
    def test_codemasters_nan_gear(self):
        b = bytearray(264)
        struct.pack_into("<f", b, 33 * 4, NAN)
        self.assertIsNone(parsers.parse_codemasters(bytes(b)))

    def test_listener_survives_garbage(self):
        frames = []
        u = UdpListener({}, frames.append)
        rnd = random.Random(3)
        for i in range(3000):
            n = rnd.choice([0, 1, 2, 24, 29, 92, 96, 264, 311, 324, 331, 1349, 1464])
            b = bytearray(rnd.randbytes(n))
            if n >= 2 and rnd.random() < 0.5:
                struct.pack_into("<H", b, 0, rnd.choice([2021, 2022, 2023]))
            u.handle(rnd.choice(["outgauge", "motionsim", "forza", "codemasters", "f1"]), bytes(b), i * 0.01)
        for f in frames:
            f.sanitize()
            json.dumps(f.to_dict(), allow_nan=False)


class TestPluginInputValidation(unittest.TestCase):
    """Values from the UI are checked before they reach the wheel or settings."""

    def test_settings_checks(self):
        import types
        import logging
        import tempfile
        tmp = tempfile.mkdtemp()
        d = types.ModuleType("decky")
        d.DECKY_PLUGIN_SETTINGS_DIR = os.path.join(tmp, "s")
        d.DECKY_PLUGIN_RUNTIME_DIR = os.path.join(tmp, "d")
        d.DECKY_USER_HOME = tmp
        d.DECKY_USER = "nobody"
        d.DECKY_PLUGIN_LOG_DIR = tmp
        d.logger = logging.getLogger("t")

        async def emit(*a):
            return None
        d.emit = emit
        sys.modules["decky"] = d
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import importlib
        main = importlib.import_module("main")
        checks = main.Plugin.SETTING_CHECKS
        self.assertTrue(checks["target_fps"](60))
        self.assertFalse(checks["target_fps"]("abc"))
        self.assertFalse(checks["target_fps"](True))
        self.assertFalse(checks["target_fps"](5))
        self.assertTrue(checks["units"]("mph"))
        self.assertFalse(checks["units"]("furlongs"))
        self.assertFalse(checks["rev_lights"]("yes"))
        p = main.Plugin.__new__(main.Plugin)
        p.settings = dict(main.DEFAULTS)
        main._save = lambda s: None
        self.assertFalse(asyncio.run(p.set_setting("target_fps", "abc")))
        self.assertTrue(asyncio.run(p.set_setting("target_fps", 90.0)))
        self.assertEqual(p.settings["target_fps"], 90)
        self.assertFalse(asyncio.run(p.wheel_set("rotation", "lots")))
        self.assertFalse(asyncio.run(p.wheel_set("rotation", math.nan)))


if __name__ == "__main__":
    unittest.main()
