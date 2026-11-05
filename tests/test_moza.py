"""Byte-for-byte check of the MOZA encoder against Boxflat, plus a simulated
wheelbase on a pty. Needs a Boxflat checkout (BOXFLAT_DIR) and PyYAML."""
import sys, os, pty, threading, time, logging, unittest
_bx = os.environ.get("BOXFLAT_DIR", "/home/claude/ext/boxflat")
try:
    import yaml
except ImportError:
    raise unittest.SkipTest("PyYAML not installed")
if not os.path.exists(os.path.join(_bx, "data", "serial.yml")):
    raise unittest.SkipTest("Boxflat checkout not found; set BOXFLAT_DIR")
import os as _o; sys.path.insert(0, _o.path.join(_o.path.dirname(_o.path.dirname(_o.path.abspath(__file__))), "py_modules", "pitwall", "wheels"))
sys.path.insert(0, _o.environ.get("BOXFLAT_DIR", "/home/claude/ext/boxflat"))
import moza
from boxflat.moza_command import MozaCommand, MOZA_COMMAND_READ, MOZA_COMMAND_WRITE

data = yaml.safe_load(open(_o.path.join(_o.environ.get("BOXFLAT_DIR", "/home/claude/ext/boxflat"), "data/serial.yml")))
names = {"rotation":"limit","ffb_strength":"ffb-strength","torque":"torque","speed":"speed","damper":"damper",
 "friction":"friction","inertia":"inertia","spring":"spring","road_sensitivity":"road-sensitivity","ffb_enabled":"ffb-disable",
 "speed_damping":"speed-damping","speed_damping_point":"speed-damping-point"}

# 1. Byte-for-byte frame comparison with Boxflat's encoder
ui = {"rotation":900,"ffb_strength":75,"torque":80,"speed":40,"damper":10,"friction":5,"inertia":150,"spring":0,"road_sensitivity":6,"ffb_enabled":1,"speed_damping":30,"speed_damping_point":120}
bx_expr = {"rotation":lambda v:v/2,"road_sensitivity":lambda v:v*4+10,"torque":lambda v:v,"ffb_enabled":lambda v:0 if v else 1,
           "speed_damping":lambda v:v,"speed_damping_point":lambda v:v}
for key, bname in names.items():
    s = moza.SETTINGS[key]
    for rw in (MOZA_COMMAND_READ, MOZA_COMMAND_WRITE):
        c = MozaCommand(); c.set_data_from_name(bname, data["commands"], "base"); c.device_id = 19
        if rw == MOZA_COMMAND_READ:
            c.set_payload(1); mine = moza.build_frame(s.read_group, 19, s.cmd_id, (1).to_bytes(s.size,"big"))
        else:
            v = round(bx_expr.get(key, lambda v: v*10)(ui[key])); c.set_payload(v)
            mine = moza.build_frame(s.write_group, 19, s.cmd_id, int(s.to_dev(ui[key])).to_bytes(s.size,"big"))
        theirs = c.prepare_message(126, rw, 13)
        assert mine == theirs, (key, rw, mine.hex(), theirs.hex())
c = MozaCommand(); c.set_data_from_name("calibration", data["commands"], "base"); c.device_id=19; c.set_payload(1)
assert c.prepare_message(126, MOZA_COMMAND_WRITE, 13) == moza.build_frame(42,19,(1,),(1).to_bytes(2,"big"))
c = MozaCommand(); c.set_data_from_name("max-angle", data["commands"], "base"); assert tuple(c.id)==(23,)
print("encoder matches Boxflat for", len(names), "settings (read+write) + calibration")

# 2. Simulated wheelbase on a pty
master, slave = pty.openpty()
store = {}  # cmd_id tuple -> raw bytes
def device():
    buf = bytearray()
    while True:
        try: chunk = os.read(master, 512)
        except OSError: return
        buf.extend(chunk)
        while True:
            i = buf.find(b"\x7e")
            if i < 0 or len(buf) < i+2: break
            del buf[:i]; n = buf[1]
            if len(buf) < n+5: break
            fr = bytes(buf[:n+5]); del buf[:n+5]
            assert fr[-1] == moza.checksum(fr[:-1]), "bad checksum from plugin"
            group, dev, body = fr[2], fr[3], fr[4:4+n]
            cid = (body[0],) if body[0] != 34 else tuple(body[:2])
            if group == 41: store[cid] = body[len(cid):]
            payload = store.get(cid, bytes(len(body)-len(cid))) if group == 40 else body[len(cid):]
            resp = bytes([0x7e, n, group | 0x80, moza.swap_nibbles(dev), *cid]) + payload
            # send garbage then the response to test resync
            os.write(master, b"\x00\x13" + resp + bytes([moza.checksum(resp)]))
threading.Thread(target=device, daemon=True).start()

b = moza.MozaBase(logger=logging.getLogger(), path_override=os.ttyname(slave))
assert b.connected()
assert b.write(ui)
assert store[(1,)] == store[(23,)] == (450).to_bytes(2,"big"), "rotation must write limit and max-angle"
got = b.read_all()
assert got == ui, (got, ui)
assert b.calibrate_center()
print("pty round-trip OK:", got)

# 3. Clamping
assert b.write({"rotation": 99999, "torque": 0})
assert b.read_all()["rotation"] == 2700 and b.read_all()["torque"] == 50
print("clamping OK")

# 4. parse_frames handles split frames
buf = bytearray(); f = moza.build_frame(40|0x80, 0x31, (2,), b"\x02\xee")
buf.extend(f[:3]); assert moza.parse_frames(buf) == []
buf.extend(f[3:]); assert moza.parse_frames(buf) == [(40, 0x13, b"\x02\x02\xee")]
print("split-frame parsing OK")
