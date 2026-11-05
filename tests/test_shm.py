"""Shared-memory readers checked against fixtures written by tools/shm_fixtures.c,
which fills the real C structs (simapi headers) with known values."""

import gzip
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "py_modules"))
FX = os.path.join(ROOT, "tests", "fixtures")

from pitwall.telemetry import shm  # noqa: E402


def load(name):
    with gzip.open(os.path.join(FX, name + ".bin.gz")) as f:
        return f.read()


class TestShmParsers(unittest.TestCase):
    def test_pcars2(self):
        f = shm.parse_pcars2(load("pcars2"))
        self.assertEqual((f.sim, f.active, f.gear, f.lap), ("ams2", True, 4, 4))
        self.assertAlmostEqual(f.speed, 55.5)
        self.assertAlmostEqual(f.throttle, 0.75)
        self.assertAlmostEqual(f.steer, -0.5)
        self.assertEqual(f.pos, (10.0, -30.0, 2.0))
        self.assertAlmostEqual(f.lap_dist, 1234.5)
        self.assertAlmostEqual(f.last_lap, 72.25)
        self.assertEqual(f.car, "Formula Vintage")
        self.assertEqual(f.track, "Interlagos GP")
        self.assertEqual(f.tyre_temp[0], 80.0)

    def test_pcars2_mid_write_rejected(self):
        b = bytearray(load("pcars2"))
        b[shm.PC2["seq"]] = 11
        self.assertIsNone(shm.parse_pcars2(bytes(b)))

    def test_rf2(self):
        f = shm.parse_rf2(load("rf2_tel"), load("rf2_scoring"))
        self.assertEqual((f.sim, f.gear, f.lap, f.car, f.track), ("rf2", 5, 3, "Oreca 07", "Spa"))
        self.assertAlmostEqual(f.speed, 5.0)            # |(3,0,-4)|
        self.assertAlmostEqual(f.lap_time, 40.0)
        self.assertAlmostEqual(f.best_lap, 125.5)
        self.assertAlmostEqual(f.lap_frac, 0.5)
        self.assertAlmostEqual(f.fuel, 0.4)
        self.assertTrue(f.active)

    def test_lmu(self):
        f = shm.parse_lmu(load("lmu"))
        self.assertEqual((f.sim, f.gear, f.lap, f.car), ("lmu", -1, 2, "Toyota GR010"))
        self.assertAlmostEqual(f.speed, 20.0)
        self.assertAlmostEqual(f.lap_time, 30.0)
        self.assertAlmostEqual(f.best_lap, 210.25)
        self.assertAlmostEqual(f.fuel, 0.1)

    def test_r3e(self):
        f = shm.parse_r3e(load("r3e"))
        self.assertEqual((f.sim, f.gear, f.lap, f.track), ("r3e", 3, 1, "Nordschleife Tourist"))
        self.assertAlmostEqual(f.rpm, 6000, delta=1)
        self.assertAlmostEqual(f.max_rpm, 8000, delta=1)
        self.assertAlmostEqual(f.last_lap, 421.0)
        self.assertEqual(f.pos, (5.0, 7.0, 6.0))
        self.assertTrue(f.active)

    def test_source_picks_up_bridge_files(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "$pcars2$"), "wb") as fh:
            fh.write(load("pcars2"))
        got = []
        src = shm.ShmSource(got.append, rate_hz=100, shm_dir=d)
        src.start()
        time.sleep(0.3)
        src.stop()
        self.assertEqual(src.active, "ams2")
        self.assertTrue(got and got[0].sim == "ams2")
        shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
