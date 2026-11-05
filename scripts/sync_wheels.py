#!/usr/bin/env python3
"""Rebuild py_modules/pitwall/data/wheels.json from the linux-steering-wheels table.

    git clone --depth 1 https://github.com/JacKeTUs/linux-steering-wheels /tmp/lsw
    python3 scripts/sync_wheels.py /tmp/lsw [YYYY-MM-DD]

linux-steering-wheels (JacKeTUs and contributors) is the community-tested source
for support ranks, drivers and Proton notes. This script only reads its compatibility
table and footnotes; Pitwall's own notes, fixes and control support are added here.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "py_modules", "pitwall", "data", "wheels.json")
SOURCE = "https://github.com/JacKeTUs/linux-steering-wheels"

BRANDS = {"Moza": "MOZA"}
PIDFF_RANGE = "in Linux 6.15+, and the 6.12.24+, 6.13.12+, 6.14.3+ updates"
# Drivers that ship with Linux. Logitech's stock driver is in, but footnotes 3 and 4
# mark models it doesn't handle; those are flipped below.
IN_KERNEL = {"hid-universal-pidff", "hid-pidff", "hid-logitech", "hid-logitech-hidpp", "hid-tmff"}

# What each footnote means for a Pitwall user, in our own words. "fix" keys tie a
# footnote to something Pitwall can check or help with.
FOOTNOTES = {
    "1": {"note": None},  # covered by the driver text
    "2": {"note": "The stock driver lacks most effects; the new-lg4ff driver adds them.", "driver_url": "https://github.com/berarma/new-lg4ff"},
    "3": {"note": "The stock driver doesn't support it; it needs the new-lg4ff driver.", "driver_url": "https://github.com/berarma/new-lg4ff", "in_kernel": False},
    "4": {"note": "The stock driver doesn't support it; it needs a patched hid-logitech-hidpp.", "driver_url": "https://github.com/JacKeTUs/hid-logitech-hidpp", "in_kernel": False},
    "5": {"note": "Uses a modified protocol; it needs the simagic-ff driver.", "driver_url": "https://github.com/JacKeTUs/simagic-ff"},
    "6": {"note": None, "driver_url": "https://github.com/gotzl/hid-fanatecff"},
    "7": {"note": "Force feedback can lag in some games when the wheel's command queue fills up. Lowering the game's FFB update rate helps; ffbwrap can also help.", "fix": "queue_full"},
    "8": {"note": None, "driver_url": "https://github.com/Kimplul/hid-tmff2"},
    "9": {"note": "Some games may not detect it as a wheel; see the detection fixes.", "fix": "detection"},
    "10": {"note": "Needs a one-time setup; see Granite Devices' Linux guide.", "link": "https://granitedevices.com/wiki/Using_Simucube_wheel_base_in_Linux"},
    "11": {"note": "Switch on high torque mode after power-on.", "link": "https://github.com/moonrail/asetek_wheelbase_cli"},
    "12": {"note": "Some units save power by disabling force feedback until the wheel is moved a little. Normal, and the same on Windows."},
    "13": {"note": "Can keep reconnecting when idle unless the kernel always polls it (a usbhid quirk on the kernel command line).", "fix": "always_poll"},
    "14": {"note": None, "driver_url": "https://github.com/NKkrisz/Thrustmaster_TMX_Linux_Driver"},
}


def clean(cell: str) -> tuple[str, list[str]]:
    notes = re.findall(r"\[\^(\d+)\]", cell)
    return re.sub(r"\[\^\d+\]", "", cell).replace("\t", " ").strip(), notes


def parse(readme: str) -> list[dict]:
    rows, in_table = [], False
    for line in readme.splitlines():
        if line.startswith("| Manufacturer"):
            in_table = True
            continue
        if in_table and not line.startswith("|"):
            break
        if not in_table or set(line) <= set("|-: "):
            continue
        cells = [c for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        (brand, _), (model, _), (vid, _), (pid, _), (rank, n1), (driver, n2), (proton, n3) = (clean(c) for c in cells[:7])
        foot = n1 + n2 + n3
        w = {"brand": BRANDS.get(brand, brand), "model": re.sub(r"\s+", " ", model) or "(DIY)",
             "vid": vid.lower() or None, "pid": pid.lower() or None,
             "rank": rank if rank in ("Platinum", "Gold", "Silver", "Bronze", "Broken") else None,
             "driver": driver or None, "in_kernel": driver in IN_KERNEL,
             "proton": None, "notes": [], "fixes": [], "driver_url": None, "links": []}
        if proton.startswith("Works"):
            w["proton"] = "Works"
        elif proton:
            w["proton"] = None
            w["notes"].append("Not tested yet; it may work out of the box if it uses the standard HID PID descriptor.")
        for n in foot:
            f = FOOTNOTES.get(n, {})
            if f.get("note") and f["note"] not in w["notes"]:
                w["notes"].append(f["note"])
            if f.get("fix") and f["fix"] not in w["fixes"]:
                w["fixes"].append(f["fix"])
            if f.get("driver_url"):
                w["driver_url"] = f["driver_url"]
            if "in_kernel" in f:
                w["in_kernel"] = f["in_kernel"]
            if f.get("link"):
                w["links"].append(f["link"])
        if w["driver"] == "hid-universal-pidff":
            w["driver"] = f"hid-universal-pidff ({PIDFF_RANGE})"
        elif w["driver"] == "hid-pidff":
            w["driver"] = f"hid-pidff (full support {PIDFF_RANGE})"
        rows.append(w)
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    repo = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else subprocess.run(
        ["git", "-C", repo, "log", "-1", "--format=%cs"], capture_output=True, text=True).stdout.strip()
    with open(os.path.join(repo, "README.md"), encoding="utf-8") as f:
        wheels = parse(f.read())
    with open(OUT, encoding="utf-8") as f:
        old = json.load(f)
    out = {
        "_about": "Wheel force feedback support on Linux. Ranks, drivers and Proton notes are summarised from the "
                  "community-tested table at linux-steering-wheels by JacKeTUs and contributors "
                  "(regenerate with scripts/sync_wheels.py). Notes, fixes and control support are Pitwall's own.",
        "source": SOURCE, "source_date": date,
        "pitwall_control": old.get("pitwall_control", {}),
        "wheels": wheels,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{len(wheels)} wheels from {SOURCE} ({date})")


if __name__ == "__main__":
    main()
