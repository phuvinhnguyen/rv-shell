#!/usr/bin/env python3
"""Shared pieces for rv's terminal apps: settings, commands and a tiny curses UI.

Standard library only. Every app follows the same keys:
  j/k or arrows  move        h/l or ←/→  change value / switch tab
  Enter          activate    Tab         next section
  r              refresh     q / Esc     quit
"""

from __future__ import annotations

import copy
import curses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Sequence

REPO = Path(os.environ.get("RV_REPO") or Path(__file__).resolve().parents[1])
DEFAULTS_FILE = REPO / "config" / "rv" / "defaults.json"
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "rv"
SETTINGS_FILE = CONFIG_HOME / "settings.json"
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "rv"


# ------------------------------------------------------------------ settings

def read_json(path: Path, fallback: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return copy.deepcopy(fallback)


def write_json(path: Path, value: Any) -> None:
    """Write atomically, so the bar's file watcher never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)


def _merge(base: dict, over: Any) -> dict:
    if not isinstance(over, dict):
        return base
    for key, value in base.items():
        wanted = over.get(key)
        if isinstance(value, dict) and isinstance(wanted, dict):
            _merge(value, wanted)
        elif wanted is not None and (type(wanted) is type(value)
                                     or (isinstance(value, float) and isinstance(wanted, int))):
            base[key] = wanted
    return base


def defaults() -> dict:
    return read_json(DEFAULTS_FILE, {})


def settings() -> dict:
    return _merge(defaults(), read_json(SETTINGS_FILE, {}))


def lookup(tree: dict, dotted: str) -> Any:
    node: Any = tree
    for part in dotted.split("."):
        node = node[part]
    return node


def set_setting(dotted: str, value: Any) -> None:
    """Store one value in settings.json; values equal to the default are dropped."""
    user = read_json(SETTINGS_FILE, {})
    if not isinstance(user, dict):
        user = {}
    parts = dotted.split(".")
    node = user
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    try:
        default = lookup(defaults(), dotted)
    except (KeyError, TypeError):
        default = object()
    if value == default:
        node.pop(parts[-1], None)
    else:
        node[parts[-1]] = value
    write_json(SETTINGS_FILE, user)


def expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


# ------------------------------------------------------------------ commands

def have(name: str) -> bool:
    return shutil.which(name) is not None


def is_gui(command: str) -> bool:
    """True when the program ships a desktop entry that does not need a terminal."""
    name = command.split()[0] if command.strip() else ""
    data = [Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share"), Path("/usr/local/share"),
            Path("/usr/share"), Path("/var/lib/flatpak/exports/share")]
    for base in data:
        entry = base / "applications" / f"{name}.desktop"
        if entry.is_file():
            return "Terminal=true" not in entry.read_text(errors="replace")
    return False


def run(cmd: Sequence[str], timeout: float = 10, input: str | None = None) -> tuple[int, str]:
    """Run a command; returns (status, combined output). Never raises."""
    try:
        result = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout, input=input)
        return result.returncode, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return 127, f"{cmd[0]}: not installed"
    except subprocess.TimeoutExpired:
        return 124, f"{cmd[0]}: timed out"


def output(cmd: Sequence[str], timeout: float = 10) -> str:
    try:
        return subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def spawn(cmd: Sequence[str]) -> None:
    subprocess.Popen(list(cmd), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def rv(*args: str) -> None:
    spawn([str(REPO / "bin" / "rv"), *args])


def notify(summary: str, body: str = "") -> None:
    if have("notify-send"):
        spawn(["notify-send", "-a", "rv", summary, body])


# -------------------------------------------------------------------- colours

def _xterm256(hexcolour: str) -> int:
    """Nearest xterm-256 colour cube index, so the TUI accent matches the bar."""
    try:
        r, g, b = (int(hexcolour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return curses.COLOR_MAGENTA
    steps = [0, 95, 135, 175, 215, 255]

    def near(v: int) -> int:
        return min(range(6), key=lambda i: abs(steps[i] - v))
    return 16 + 36 * near(r) + 6 * near(g) + near(b)


TITLE, SELECTED, DIM, GOOD, WARN, BAD, ACCENT, BAR = range(1, 9)


def init_colours() -> None:
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    theme = settings().get("theme", {})
    many = curses.COLORS >= 256

    def pick(key: str, fallback: int) -> int:
        return _xterm256(theme.get(key, "")) if many else fallback
    accent = pick("accent", curses.COLOR_MAGENTA)
    curses.init_pair(TITLE, accent, bg)
    curses.init_pair(SELECTED, 16 if many else curses.COLOR_BLACK, accent)
    curses.init_pair(DIM, 245 if many else curses.COLOR_WHITE, bg)
    curses.init_pair(GOOD, pick("good", curses.COLOR_GREEN), bg)
    curses.init_pair(WARN, pick("warn", curses.COLOR_YELLOW), bg)
    curses.init_pair(BAD, pick("bad", curses.COLOR_RED), bg)
    curses.init_pair(ACCENT, accent, bg)
    curses.init_pair(BAR, 252 if many else curses.COLOR_WHITE, 236 if many else bg)


def attr(pair: int, extra: int = 0) -> int:
    return curses.color_pair(pair) | extra


# ------------------------------------------------------------------------ UI

class Row:
    """One line in a list: a label, a right-aligned value and a colour."""

    def __init__(self, label: str, value: str = "", *, data: Any = None, colour: int = 0,
                 icon: str = "", header: bool = False, hint: str = ""):
        self.label, self.value, self.data = label, value, data
        self.colour, self.icon, self.header, self.hint = colour, icon, header, hint


class App:
    """Base for every rv terminal app.

    Subclasses set `title`, `tabs` (optional), implement `rows()` and
    `on_key(key, row)`, and may override `refresh()` (called every
    `interval` seconds and on `r`).
    """

    title = "rv"
    tabs: list[str] = []
    interval = 0.0
    keys_hint = ""
    quit_hint = "q quit"

    def __init__(self) -> None:
        self.tab = 0
        self.index = 0
        self.scroll = 0
        self.message = ""
        self.message_colour = DIM
        self.message_until = 0.0
        self.running = True
        self.screen: Any = None
        self.last_refresh = 0.0

    # Subclass hooks ---------------------------------------------------------
    def refresh(self) -> None:
        pass

    def rows(self) -> list[Row]:
        return []

    def on_key(self, key: int, row: Row | None) -> None:
        pass

    def detail(self, row: Row | None) -> list[str]:
        """Optional lines shown under the list for the selected row."""
        return []

    def intercept(self, key: int) -> int | None:
        """See a key before the standard handling; return None to swallow it."""
        return key

    # Helpers -----------------------------------------------------------------
    def flash(self, text: str, colour: int = DIM, seconds: float = 4) -> None:
        self.message, self.message_colour = text, colour
        self.message_until = time.monotonic() + seconds

    def busy(self, text: str) -> None:
        self.flash(text, WARN, 30)
        self.draw()

    def selectable(self) -> list[int]:
        return [i for i, r in enumerate(self._rows) if not r.header]

    def selected(self) -> Row | None:
        if 0 <= self.index < len(self._rows) and not self._rows[self.index].header:
            return self._rows[self.index]
        return None

    def move(self, step: int) -> None:
        options = self.selectable()
        if not options:
            return
        if self.index not in options:
            self.index = options[0]
            return
        position = options.index(self.index) + step
        self.index = options[max(0, min(len(options) - 1, position))]

    def put(self, y: int, x: int, text: str, width: int, attribute: int = 0) -> None:
        if width <= 0 or y < 0:
            return
        h, w = self.screen.getmaxyx()
        if y >= h or x >= w:
            return
        text = text.replace("\n", " ")
        if len(text) > width:
            text = text[:max(0, width - 1)] + "…"
        try:
            self.screen.addstr(y, x, text, attribute)
        except curses.error:
            pass

    # Drawing -----------------------------------------------------------------
    def draw(self) -> None:
        s = self.screen
        s.erase()
        h, w = s.getmaxyx()
        # Title line and tabs.
        self.put(0, 2, self.title, w - 4, attr(TITLE, curses.A_BOLD))
        x = len(self.title) + 5
        for i, name in enumerate(self.tabs):
            label = f" {name} "
            self.put(0, x, label, w - x, attr(SELECTED, curses.A_BOLD) if i == self.tab else attr(DIM))
            x += len(label) + 1
        self.put(1, 2, "─" * (w - 4), w - 4, attr(DIM))

        rows = self._rows
        details = self.detail(self.selected())
        list_height = max(1, h - 5 - (len(details) + 1 if details else 0))
        if self.index < self.scroll:
            self.scroll = self.index
        if self.index >= self.scroll + list_height:
            self.scroll = self.index - list_height + 1
        self.scroll = max(0, min(self.scroll, max(0, len(rows) - list_height)))
        value_width = min(max((len(r.value) for r in rows), default=0), max(10, w // 2 - 4))
        for line, i in enumerate(range(self.scroll, min(len(rows), self.scroll + list_height))):
            row = rows[i]
            y = 2 + line
            if row.header:
                self.put(y, 2, row.label, w - 4, attr(ACCENT, curses.A_BOLD))
                continue
            chosen = i == self.index
            base = attr(SELECTED) if chosen else (attr(row.colour) if row.colour else 0)
            if chosen:
                self.put(y, 2, " " * (w - 4), w - 4, base)
            icon = (row.icon + " ") if row.icon else ""
            self.put(y, 3, icon + row.label, w - value_width - 8, base | (curses.A_BOLD if chosen else 0))
            if row.value:
                vx = w - 3 - min(len(row.value), value_width)
                self.put(y, vx, row.value, value_width, base if chosen else attr(DIM) | (attr(row.colour) if row.colour else 0))
        if not rows:
            self.put(3, 4, "Nothing here yet.", w - 8, attr(DIM))
        if details:
            top = h - 3 - len(details)
            self.put(top - 1, 2, "─" * (w - 4), w - 4, attr(DIM))
            for n, line in enumerate(details):
                self.put(top + n, 3, line, w - 6, attr(DIM))
        # Footer: message or key hints.
        self.put(h - 2, 2, "─" * (w - 4), w - 4, attr(DIM))
        if self.message and time.monotonic() < self.message_until:
            self.put(h - 1, 2, self.message, w - 4, attr(self.message_colour, curses.A_BOLD))
        else:
            hint = self.keys_hint + ("  ·  " if self.keys_hint else "") + self.quit_hint
            self.put(h - 1, 2, hint, w - 4, attr(DIM))
        s.refresh()

    # Input widgets -------------------------------------------------------------
    def prompt(self, label: str, initial: str = "", secret: bool = False) -> str | None:
        """Single-line input on the footer. Esc cancels (None)."""
        s = self.screen
        text = list(initial)
        curses.curs_set(1)
        s.timeout(-1)
        try:
            while True:
                h, w = s.getmaxyx()
                shown = ("•" * len(text)) if secret else "".join(text)
                field = w - len(label) - 7
                shown = shown[-field:] if field > 0 else ""
                s.move(h - 1, 0)
                s.clrtoeol()
                self.put(h - 1, 2, label + ": ", w - 4, attr(ACCENT, curses.A_BOLD))
                self.put(h - 1, 4 + len(label), shown, field + 1)
                s.move(h - 1, min(w - 2, 4 + len(label) + len(shown)))
                key = s.get_wch()
                if key in ("\n", "\r", curses.KEY_ENTER):
                    return "".join(text)
                if key == "\x1b":
                    return None
                if key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                    if text:
                        text.pop()
                elif key == "\x15":  # Ctrl+U
                    text.clear()
                elif isinstance(key, str) and key.isprintable():
                    text.append(key)
        finally:
            curses.curs_set(0)
            s.timeout(self._timeout())

    def confirm(self, question: str) -> bool:
        s = self.screen
        h, w = s.getmaxyx()
        s.move(h - 1, 0)
        s.clrtoeol()
        self.put(h - 1, 2, f"{question}? [y/N]", w - 4, attr(WARN, curses.A_BOLD))
        s.timeout(-1)
        try:
            return s.getch() in (ord("y"), ord("Y"))
        finally:
            s.timeout(self._timeout())

    def choose(self, title: str, options: Sequence[str], current: str | None = None) -> str | None:
        """A centred pick-list box. Returns the option or None."""
        if not options:
            return None
        s = self.screen
        index = options.index(current) if current in options else 0
        s.timeout(-1)
        try:
            while True:
                h, w = s.getmaxyx()
                bw = min(w - 4, max(len(title) + 6, max(len(o) for o in options) + 8))
                bh = min(h - 4, len(options) + 4)
                y0, x0 = (h - bh) // 2, (w - bw) // 2
                visible = bh - 4
                top = max(0, min(index - visible // 2, len(options) - visible))
                win = curses.newwin(bh, bw, y0, x0)
                win.attron(attr(ACCENT))
                win.box()
                win.attroff(attr(ACCENT))
                try:
                    win.addstr(1, 2, title[:bw - 4], attr(TITLE, curses.A_BOLD))
                    for n, option in enumerate(options[top:top + visible]):
                        chosen = top + n == index
                        win.addstr(3 + n, 2, f" {option} ".ljust(bw - 4)[:bw - 4],
                                   attr(SELECTED) if chosen else 0)
                except curses.error:
                    pass
                win.refresh()
                key = s.getch()
                if key in (ord("j"), curses.KEY_DOWN):
                    index = min(len(options) - 1, index + 1)
                elif key in (ord("k"), curses.KEY_UP):
                    index = max(0, index - 1)
                elif key in (10, 13, curses.KEY_ENTER, ord("l"), curses.KEY_RIGHT):
                    return options[index]
                elif key in (27, ord("q"), ord("h"), curses.KEY_LEFT):
                    return None
        finally:
            s.timeout(self._timeout())
            self.screen.touchwin()

    # Loop ----------------------------------------------------------------------
    def _timeout(self) -> int:
        return int(self.interval * 1000) if self.interval else 1000

    def start(self) -> None:
        curses.wrapper(self._main)

    def _main(self, screen: Any) -> None:
        self.screen = screen
        curses.curs_set(0)
        os.environ.setdefault("ESCDELAY", "25")
        curses.set_escdelay(25)
        init_colours()
        screen.keypad(True)
        screen.timeout(self._timeout())
        self.busy("Loading…")
        self.refresh()
        self.message = ""
        self.last_refresh = time.monotonic()
        while self.running:
            self._rows = self.rows()
            if self.index >= len(self._rows) or (self._rows and self._rows[self.index].header):
                self.index = min(self.index, max(0, len(self._rows) - 1))
                self.move(0)
                if self.selected() is None:
                    self.move(1)
            self.draw()
            key = screen.getch()
            if key == -1:
                if self.interval and time.monotonic() - self.last_refresh >= self.interval:
                    self.refresh()
                    self.last_refresh = time.monotonic()
                continue
            if key == curses.KEY_RESIZE:
                continue
            key = self.intercept(key)
            if key is None:
                continue
            if key in (ord("q"), 27):
                self.running = False
            elif key in (ord("j"), curses.KEY_DOWN):
                self.move(1)
            elif key in (ord("k"), curses.KEY_UP):
                self.move(-1)
            elif key in (curses.KEY_NPAGE,):
                self.move(10)
            elif key in (curses.KEY_PPAGE,):
                self.move(-10)
            elif key in (ord("g"), curses.KEY_HOME):
                self.index = 0
                self.move(0)
            elif key in (ord("G"), curses.KEY_END):
                self.index = len(self._rows) - 1
                self.move(0)
            elif key == 9 and self.tabs:
                self.tab = (self.tab + 1) % len(self.tabs)
                self.index = self.scroll = 0
            elif key == curses.KEY_BTAB and self.tabs:
                self.tab = (self.tab - 1) % len(self.tabs)
                self.index = self.scroll = 0
            elif key == ord("r"):
                self.busy("Refreshing…")
                self.refresh()
                self.flash("Refreshed")
                self.last_refresh = time.monotonic()
            else:
                self.on_key(key, self.selected())

    _rows: list[Row] = []


ENTER = (10, 13, curses.KEY_ENTER)
LEFT = (ord("h"), curses.KEY_LEFT)
RIGHT = (ord("l"), curses.KEY_RIGHT)


def main_cli(argv: list[str]) -> int:
    """`python3 rvlib.py get bar.width` — used by bin/rv."""
    if len(argv) == 3 and argv[1] == "get":
        try:
            value = lookup(settings(), argv[2])
        except (KeyError, TypeError):
            return 1
        print(json.dumps(value) if isinstance(value, (dict, list, bool)) else value)
        return 0
    if len(argv) == 4 and argv[1] == "set":
        try:
            value: Any = json.loads(argv[3])
        except ValueError:
            value = argv[3]
        set_setting(argv[2], value)
        return 0
    print("usage: rvlib.py get KEY | set KEY VALUE", file=sys.stderr)
    return 2


def guard(app_main: Callable[[], Any]) -> None:
    """Run an app's main and turn Ctrl+C into a quiet exit."""
    try:
        app_main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    raise SystemExit(main_cli(sys.argv))
