#!/usr/bin/env python3
"""rv bluetooth: BlueZ in a terminal (bluetoothctl underneath).

Enter connect/disconnect (pairs new devices) · s scan · p power on/off
x remove device · q quit
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402
from rvlib import Row  # noqa: E402

ICONS = {
    "audio-headset": "\U000f02cb", "audio-headphones": "\U000f02cb", "audio-card": "\U000f04c3",
    "input-keyboard": "\U000f030c", "input-mouse": "\U000f037d", "input-gaming": "\U000f0297",
    "phone": "\U000f03f2", "computer": "\U000f0322",
}


AUDIO_PLUGIN = Path("/usr/lib/x86_64-linux-gnu/spa-0.2/bluez5")


def ctl(*args: str, timeout: float = 10) -> tuple[int, str]:
    return rvlib.run(["bluetoothctl", *args], timeout=timeout)


class BluetoothApp(rvlib.App):
    title = "Bluetooth"
    interval = 2
    keys_hint = "Enter connect/disconnect · s scan · p power · x remove"

    def __init__(self) -> None:
        super().__init__()
        self.powered = False
        self.adapter = ""
        self.devices: list[dict] = []
        self.scanner: subprocess.Popen | None = None
        self.scan_until = 0.0

    def refresh(self) -> None:
        if not rvlib.have("bluetoothctl"):
            self.flash("bluetoothctl not found: install bluez", rvlib.BAD, 60)
            return
        _, show = ctl("show")
        if "No default controller" in show or not show:
            self.adapter = ""
            self.powered = False
            self.devices = []
            return
        self.powered = "Powered: yes" in show
        self.adapter = next((l.split(":", 1)[1].strip() for l in show.splitlines() if l.strip().startswith("Alias:")), "adapter")
        devices = []
        _, listing = ctl("devices")
        for line in listing.splitlines():
            parts = line.split(" ", 2)
            if len(parts) < 3 or parts[0] != "Device":
                continue
            _, info = ctl("info", parts[1])
            fields = {}
            for raw in info.splitlines():
                key, sep, value = raw.strip().partition(": ")
                if sep:
                    fields[key] = value
            battery = fields.get("Battery Percentage", "")
            devices.append({
                "mac": parts[1], "name": fields.get("Alias", parts[2]),
                "paired": fields.get("Paired") == "yes", "connected": fields.get("Connected") == "yes",
                "trusted": fields.get("Trusted") == "yes", "icon": fields.get("Icon", ""),
                "battery": battery.split("(")[-1].rstrip(")") + "%" if "(" in battery else "",
                "rssi": fields.get("RSSI", ""),
            })
        self.devices = sorted(devices, key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
        if self.scanner and (self.scanner.poll() is not None or time.monotonic() > self.scan_until):
            self.stop_scan()

    def stop_scan(self) -> None:
        if self.scanner and self.scanner.poll() is None:
            self.scanner.terminate()
        self.scanner = None

    def rows(self) -> list[Row]:
        if not self.adapter:
            return [Row("No Bluetooth adapter found", colour=rvlib.DIM)]
        scanning = " · scanning…" if self.scanner else ""
        rows = [Row(f"{self.adapter} · {'on' if self.powered else 'off'}{scanning}", header=True)]
        if not self.powered:
            rows.append(Row("Bluetooth is off — press p to turn it on", colour=rvlib.DIM))
            return rows
        paired = [d for d in self.devices if d["paired"]]
        others = [d for d in self.devices if not d["paired"]]
        for title, group in (("My devices", paired), ("Nearby", others)):
            if not group:
                continue
            rows.append(Row(title, header=True))
            for d in group:
                state = "connected" if d["connected"] else ("paired" if d["paired"] else "")
                value = "  ".join(v for v in (d["battery"], state) if v)
                rows.append(Row(d["name"], value, data=d, icon=ICONS.get(d["icon"], "\U000f00af"),
                                colour=rvlib.GOOD if d["connected"] else 0))
        if not others:
            rows.append(Row("Press s to look for new devices", colour=rvlib.DIM))
        return rows

    def detail(self, row: Row | None) -> list[str]:
        if row is None or not row.data:
            return []
        d = row.data
        if d["icon"].startswith("audio") and not AUDIO_PLUGIN.exists():
            return ["Audio devices need PipeWire's Bluetooth plugin: sudo apt install libspa-0.2-bluetooth",
                    "then: systemctl --user restart pipewire wireplumber"]
        return [f"{d['mac']}   trusted: {'yes' if d['trusted'] else 'no'}" + (f"   signal: {d['rssi']}" if d["rssi"] else "")]

    def act(self, message: str, *args: str, timeout: float = 25) -> bool:
        self.busy(message)
        status, out = ctl(*args, timeout=timeout)
        ok = status == 0 and "Failed" not in out and "not available" not in out
        lines = [l for l in out.splitlines() if l.strip()]
        self.flash(lines[-1] if lines else ("Done" if ok else "Failed"), rvlib.GOOD if ok else rvlib.BAD, 6)
        self.refresh()
        return ok

    def on_key(self, key: int, row: Row | None) -> None:
        d = row.data if row else None
        if key in rvlib.ENTER and d:
            if d["connected"]:
                self.act(f"Disconnecting {d['name']}…", "disconnect", d["mac"])
                return
            if not d["paired"]:
                self.stop_scan()
                # Pairing needs the adapter pairable and an agent to answer the
                # handshake; earbuds and speakers use "just works" (no PIN).
                ctl("pairable", "on")
                if not self.act(f"Pairing {d['name']}… (put it in pairing mode)",
                                "--agent", "NoInputNoOutput", "--timeout", "30", "pair", d["mac"], timeout=35):
                    return
                ctl("trust", d["mac"])
            self.act(f"Connecting {d['name']}…", "connect", d["mac"])
        elif key == ord("s"):
            if self.scanner:
                self.stop_scan()
                self.flash("Scan stopped")
                return
            self.scanner = subprocess.Popen(["bluetoothctl", "--timeout", "30", "scan", "on"],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.scan_until = time.monotonic() + 30
            self.flash("Scanning for 30 s…", rvlib.WARN)
        elif key == ord("p"):
            if not self.powered:
                rvlib.run(["rfkill", "unblock", "bluetooth"])
            self.act("Switching…", "power", "off" if self.powered else "on")
        elif key == ord("x") and d:
            if self.confirm(f"Remove {d['name']}"):
                self.act("Removing…", "remove", d["mac"])

    def _main(self, screen) -> None:
        try:
            super()._main(screen)
        finally:
            self.stop_scan()


if __name__ == "__main__":
    rvlib.guard(BluetoothApp().start)
