"""
Drives a wheel's rev lights from live telemetry (MOZA wheels with RPM LEDs).

10 LEDs fill from 60% to 97% of max RPM; above that (or when the sim says
"shift") they all flash. Frames are only sent when the pattern changes, so
the serial traffic is small.
"""

from __future__ import annotations

import threading
import time

N_LEDS = 10
START = 0.60
FULL = 0.97
FLASH_HZ = 8


def led_mask(rpm: float, max_rpm: float | None, shift: bool, now: float) -> int:
    if not max_rpm or max_rpm <= 0 or rpm <= 0:
        return 0
    frac = rpm / max_rpm
    if shift or frac >= FULL:
        return (1 << N_LEDS) - 1 if int(now * FLASH_HZ * 2) % 2 == 0 else 0
    lit = int(max(0.0, (frac - START) / (FULL - START)) * N_LEDS + 0.5)
    lit = max(0, min(N_LEDS, lit))
    return (1 << lit) - 1


class RevLights(threading.Thread):
    def __init__(self, hub, get_wheel, rate_hz: float = 30.0):
        super().__init__(daemon=True, name="rev-lights")
        self.hub, self.get_wheel = hub, get_wheel
        self.period = 1.0 / rate_hz
        self._stop = threading.Event()
        self._observed_max = 0.0
        self._sim = None

    def stop(self):
        self._stop.set()

    def run(self):
        wheel, last, engaged = None, None, False
        while not self._stop.is_set():
            f = self.hub.frame
            fresh = f is not None and time.monotonic() - f.t < 1.0 and f.active
            if not fresh:
                if engaged and wheel:
                    wheel.leds(0)
                    wheel.leds_end()
                    engaged, last = False, None
                self._stop.wait(0.5)
                continue
            if wheel is None or not engaged:
                wheel = self.get_wheel()
                if not wheel or not getattr(wheel, "leds_supported", False):
                    self._stop.wait(2.0)
                    continue
                engaged = wheel.leds_begin()
            if f.sim != self._sim:
                self._sim, self._observed_max = f.sim, 0.0
            self._observed_max = max(self._observed_max * 0.99995, f.rpm)
            mask = led_mask(f.rpm, f.max_rpm or self._observed_max, f.shift_light, time.monotonic())
            if mask != last:
                if not wheel.leds(mask):
                    engaged = False
                last = mask
            self._stop.wait(self.period)
        if engaged and wheel:
            wheel.leds(0)
            wheel.leds_end()
