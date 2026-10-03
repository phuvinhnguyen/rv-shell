#!/usr/bin/env python3
"""rv audio: PipeWire volume control in a terminal (pactl underneath).

Tab section · h/l volume -/+5% · H/L ±1% · m mute · Enter make default
(in Apps: move the stream to another output) · q quit
"""

from __future__ import annotations

import curses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402
from rvlib import Row  # noqa: E402


def pactl_json(kind: str) -> list[dict]:
    status, out = rvlib.run(["pactl", "-f", "json", "list", kind])
    try:
        return json.loads(out) if status == 0 else []
    except ValueError:
        return []


def percent(entry: dict) -> int:
    channels = entry.get("volume", {}).values()
    values = [int(str(c.get("value_percent", "0")).rstrip("%") or 0) for c in channels]
    return round(sum(values) / len(values)) if values else 0


def meter(value: int, width: int = 20) -> str:
    filled = min(width, round(value / 100 * width))
    return "█" * filled + "░" * (width - filled) + (" +" if value > 100 else "  ")


class AudioApp(rvlib.App):
    title = "Audio"
    tabs = ["Output", "Input", "Apps"]
    interval = 1.5
    keys_hint = "h/l volume · m mute · Enter default/move"

    def __init__(self) -> None:
        super().__init__()
        self.sinks: list[dict] = []
        self.sources: list[dict] = []
        self.streams: list[dict] = []
        self.default_sink = ""
        self.default_source = ""

    def refresh(self) -> None:
        if not rvlib.have("pactl"):
            self.flash("pactl not found: install pulseaudio-utils", rvlib.BAD, 60)
            return
        self.sinks = pactl_json("sinks")
        self.sources = [s for s in pactl_json("sources") if not s.get("name", "").endswith(".monitor")]
        self.streams = pactl_json("sink-inputs")
        self.default_sink = rvlib.output(["pactl", "get-default-sink"]).strip()
        self.default_source = rvlib.output(["pactl", "get-default-source"]).strip()

    def device_rows(self, devices: list[dict], default: str, kind: str) -> list[Row]:
        rows = []
        for d in devices:
            vol = percent(d)
            mark = "\U000f0581" if d.get("mute") else ("\U000f057e" if kind == "sink" else "\U000f036c")
            name = d.get("description") or d.get("name")
            rows.append(Row(name + ("  · default" if d.get("name") == default else ""),
                            f"{meter(vol)}{vol:>4}%" + (" muted" if d.get("mute") else ""),
                            data=(kind, d), icon=mark,
                            colour=rvlib.DIM if d.get("mute") else (rvlib.GOOD if d.get("name") == default else 0)))
        return rows or [Row("No devices", colour=rvlib.DIM)]

    def rows(self) -> list[Row]:
        if self.tab == 0:
            return self.device_rows(self.sinks, self.default_sink, "sink")
        if self.tab == 1:
            return self.device_rows(self.sources, self.default_source, "source")
        rows = []
        sink_names = {s.get("index"): s.get("description", "") for s in self.sinks}
        for s in self.streams:
            props = s.get("properties", {})
            name = props.get("application.name") or props.get("media.name") or f"stream {s.get('index')}"
            vol = percent(s)
            rows.append(Row(name, f"{meter(vol)}{vol:>4}%" + (" muted" if s.get("mute") else ""),
                            data=("sink-input", s), icon="\U000f075a",
                            hint=f"{props.get('media.name', '')} → {sink_names.get(s.get('sink'), '')}",
                            colour=rvlib.DIM if s.get("mute") else 0))
        return rows or [Row("Nothing is playing", colour=rvlib.DIM)]

    def detail(self, row: Row | None) -> list[str]:
        if row is None or not row.data:
            return []
        kind, entry = row.data
        if kind == "sink-input":
            return [row.hint]
        return [entry.get("name", "")]

    def on_key(self, key: int, row: Row | None) -> None:
        if row is None or not row.data:
            return
        kind, entry = row.data
        target = str(entry.get("index")) if kind == "sink-input" else entry.get("name")
        step = {ord("h"): "-5%", curses.KEY_LEFT: "-5%", ord("l"): "+5%", curses.KEY_RIGHT: "+5%",
                ord("H"): "-1%", ord("L"): "+1%"}.get(key)
        if step:
            if step.startswith("+") and percent(entry) >= 150:
                return
            rvlib.run(["pactl", f"set-{kind}-volume", target, step])
        elif key == ord("m"):
            rvlib.run(["pactl", f"set-{kind}-mute", target, "toggle"])
        elif key in rvlib.ENTER:
            if kind == "sink-input":
                names = [s.get("description") or s.get("name") for s in self.sinks]
                picked = self.choose("Move to output", names)
                if picked:
                    sink = self.sinks[names.index(picked)]
                    rvlib.run(["pactl", "move-sink-input", target, sink.get("name")])
            else:
                rvlib.run(["pactl", f"set-default-{kind}", target])
                self.flash(f"Default {('output' if kind == 'sink' else 'input')}: {entry.get('description')}", rvlib.GOOD)
        else:
            return
        self.refresh()


if __name__ == "__main__":
    rvlib.guard(AudioApp().start)
