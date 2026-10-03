#!/usr/bin/env python3
"""rv emoji: type to search, Enter copies (and the window closes).

The list comes from Python's own Unicode database — no extra packages.
Recently used emoji are listed first.
"""

from __future__ import annotations

import curses
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402
from rvlib import Row  # noqa: E402

RECENT = rvlib.DATA_HOME / "emoji-recent.json"
RANGES = [(0x1F600, 0x1F64F), (0x1F300, 0x1F5FF), (0x1F680, 0x1F6FF), (0x1F900, 0x1F9FF),
          (0x1FA70, 0x1FAFF), (0x2600, 0x26FF), (0x2700, 0x27BF), (0x1F1E6, 0x1F1FF), (0x2B50, 0x2B55)]


def catalogue() -> list[tuple[str, str]]:
    out = []
    for low, high in RANGES:
        for code in range(low, high + 1):
            name = unicodedata.name(chr(code), "")
            if name:
                out.append((chr(code), name.lower()))
    return out


class EmojiApp(rvlib.App):
    title = "Emoji"
    keys_hint = "type to search · ↑/↓ move · Enter copy"
    quit_hint = "Esc clear, then quit"

    def __init__(self) -> None:
        super().__init__()
        self.all = catalogue()
        self.recent: list[str] = rvlib.read_json(RECENT, []) or []
        self.query = ""

    def rows(self) -> list[Row]:
        words = self.query.lower().split()
        if not words:
            recent = [(e, n) for e in self.recent for c, n in self.all if c == e]
            rows = [Row("Recent", header=True)] if recent else []
            rows += [Row(f"{e}   {n}", data=e) for e, n in recent]
            rows.append(Row("All", header=True))
            rows += [Row(f"{e}   {n}", data=e) for e, n in self.all[:400]]
            return rows
        # Every typed word must start a word of the name: "cat" finds cat faces, not "location".
        hits = [(e, n) for e, n in self.all
                if all(any(part.startswith(w) for part in n.split()) for w in words)]
        hits.sort(key=lambda en: (not en[1].startswith(words[0]), len(en[1])))
        return [Row(f"search: {self.query}", header=True)] + [Row(f"{e}   {n}", data=e) for e, n in hits[:300]]

    def intercept(self, key: int) -> int | None:
        if key == 27 and self.query:
            self.query = ""
            return None
        if key in (curses.KEY_BACKSPACE, 127, 8):
            self.query = self.query[:-1]
            return None
        if 32 <= key < 127:
            self.query += chr(key)
            self.index = self.scroll = 0
            return None
        return key

    def on_key(self, key: int, row: Row | None) -> None:
        if key in rvlib.ENTER and row and row.data:
            emoji = row.data
            subprocess.run(["wl-copy", emoji])
            self.recent = [emoji] + [e for e in self.recent if e != emoji]
            rvlib.write_json(RECENT, self.recent[:24])
            rvlib.notify("Emoji copied", emoji)
            self.running = False


if __name__ == "__main__":
    rvlib.guard(EmojiApp().start)
