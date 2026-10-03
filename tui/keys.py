#!/usr/bin/env python3
"""rv keys: every Hyprland binding, read live from `hyprctl binds`.

Type to filter · Esc clears the filter, then quits.
"""

from __future__ import annotations

import curses
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402
from rvlib import Row  # noqa: E402

MODS = [(64, "SUPER"), (4, "CTRL"), (8, "ALT"), (1, "SHIFT")]
NAMES = {"mouse:272": "left drag", "mouse:273": "right drag", "mouse_down": "scroll down", "mouse_up": "scroll up",
         "RETURN": "Enter", "COMMA": ",", "PERIOD": ".", "SLASH": "/", "ESCAPE": "Esc", "TAB": "Tab", "PRINT": "Print"}


def combo(bind: dict) -> str:
    mods = [name for bit, name in MODS if bind.get("modmask", 0) & bit]
    key = bind.get("key", "")
    return " + ".join(mods + [NAMES.get(key, key.replace("XF86", "").replace("Audio", "Audio "))])


def load() -> list[tuple[str, str]]:
    try:
        binds = json.loads(rvlib.output(["hyprctl", "binds", "-j"]))
    except ValueError:
        return []
    items: list[tuple[str, str]] = []
    # Collapse numbered runs ("Workspace 1" … "Workspace 10") into one line.
    groups: dict[tuple, list[tuple[str, int]]] = {}
    order: list[tuple] = []
    for bind in binds:
        text = bind.get("description") or ""
        if not text:
            continue
        keys = combo(bind)
        match = re.fullmatch(r"(.*?)(\d+)", text)
        if match and re.fullmatch(r".*\b\d", keys):
            group = (match.group(1), re.sub(r"\d$", "#", keys))
            if group not in groups:
                groups[group] = []
                order.append(group)
            groups[group].append((keys, int(match.group(2))))
            continue
        order.append((text, keys))
    for entry in order:
        if entry in groups:
            numbers = groups[entry]
            first, last = numbers[0], numbers[-1]
            keys = entry[1].replace("#", f"{first[0][-1]}…{last[0][-1]}")
            items.append((keys, f"{entry[0]}{first[1]}–{last[1]}"))
        else:
            items.append((entry[1], entry[0]))
    return items


class KeysApp(rvlib.App):
    title = "Keybindings"
    keys_hint = "type to filter · ↑/↓ move"
    quit_hint = "Esc clear, then quit"

    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self.query = ""

    def refresh(self) -> None:
        self.items = load()

    def rows(self) -> list[Row]:
        q = self.query.lower()
        rows = [Row(f"filter: {self.query}" if q else f"{len(self.items)} bindings", header=True)]
        for keys, text in self.items:
            if not q or q in keys.lower() or q in text.lower():
                rows.append(Row(text, keys, data=keys))
        return rows

    def intercept(self, key: int) -> int | None:
        if key == 27:
            if self.query:
                self.query = ""
                return None
            return key
        if key in (curses.KEY_BACKSPACE, 127, 8):
            self.query = self.query[:-1]
            return None
        if 32 <= key < 127:
            self.query += chr(key)
            self.index = self.scroll = 0
            return None
        return key


if __name__ == "__main__":
    rvlib.guard(KeysApp().start)
