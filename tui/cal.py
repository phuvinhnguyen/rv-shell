#!/usr/bin/env python3
"""rv calendar: month view with your own events plus synced calendars.

Your events are kept in ~/.local/share/rv/calendar.json. Other calendars —
Google, Outlook/Microsoft 365, shared or public ICS links, downloaded .ics
files, everything in Evolution — are synced read-only by tui/calsync.py.
Both show in the bar's clock popup.

h/j/k/l or arrows move by day/week · H/L or [ ] month · t today
a add event · Enter/e edit · x delete · J/K choose event
c calendars (add/remove) · S sync now · E open Evolution · q quit
"""

from __future__ import annotations

import calendar
import curses
import datetime as dt
import re
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402

DATA = rvlib.DATA_HOME / "calendar.json"
SYNCED = rvlib.DATA_HOME / "calendar-sync.json"
SYNC = Path(__file__).resolve().parent / "calsync.py"
REPEATS = ["none", "daily", "weekly", "monthly", "yearly"]


def load() -> list[dict]:
    data = rvlib.read_json(DATA, {})
    return data.get("events", []) if isinstance(data, dict) else []


def occurs(event: dict, day: dt.date) -> bool:
    try:
        start = dt.date.fromisoformat(event.get("date", ""))
    except ValueError:
        return False
    if day < start:
        return False
    repeat = event.get("repeat", "none")
    if repeat == "daily":
        return True
    if repeat == "weekly":
        return day.weekday() == start.weekday()
    if repeat == "monthly":
        return day.day == start.day
    if repeat == "yearly":
        return (day.month, day.day) == (start.month, start.day)
    return day == start


class CalendarApp(rvlib.App):
    title = "Calendar"
    keys_hint = "a add · e edit · x delete · H/L month · c calendars · S sync"
    interval = 1.5

    def __init__(self) -> None:
        super().__init__()
        self.day = dt.date.today()
        self.events: list[dict] = []
        self.synced: dict[str, list[dict]] = {}
        self.sync_report: list[dict] = []
        self.syncing: subprocess.Popen | None = None
        self.pick = 0
        self.started = False

    def sources(self) -> list[dict]:
        found = rvlib.settings().get("calendar", {}).get("sources", [])
        return found if isinstance(found, list) else []

    def refresh(self) -> None:
        self.events = load()
        data = rvlib.read_json(SYNCED, {}) or {}
        by_day: dict[str, list[dict]] = {}
        for e in data.get("events", []):
            by_day.setdefault(e.get("date", ""), []).append(e)
        self.synced = by_day
        self.sync_report = data.get("sources", [])
        if self.syncing and self.syncing.poll() is not None:
            self.syncing = None
            failed = [r for r in self.sync_report if not r.get("ok")]
            if failed:
                self.flash(f"{failed[0]['name']}: {failed[0].get('error', 'failed')}", rvlib.BAD, 10)
            else:
                self.flash("Calendars synced", rvlib.GOOD)
        if not self.started:
            self.started = True
            if self.sources():
                self.sync()

    def sync(self) -> None:
        """Runs in the background; the view updates when it finishes."""
        if self.syncing is None and self.sources():
            self.syncing = subprocess.Popen([sys.executable, str(SYNC)], stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL)
            self.flash("Syncing calendars…", rvlib.WARN, 30)

    def save(self) -> None:
        rvlib.write_json(DATA, {"events": self.events})

    def on_day(self, day: dt.date) -> list[dict]:
        mine = [e for e in self.events if occurs(e, day)]
        return sorted(mine + self.synced.get(day.isoformat(), []), key=lambda e: e.get("time") or "")

    def draw(self) -> None:
        s = self.screen
        s.erase()
        h, w = s.getmaxyx()
        A = rvlib.attr
        self.put(0, 2, self.title, w - 4, A(rvlib.TITLE, curses.A_BOLD))
        self.put(0, 14, self.day.strftime("%B %Y"), w - 16, A(rvlib.ACCENT, curses.A_BOLD))
        self.put(1, 2, "─" * (w - 4), w - 4, A(rvlib.DIM))
        today = dt.date.today()
        cell = 5
        x0 = 3
        for i, name in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            self.put(3, x0 + i * cell, f"{name:>3}", cell, A(rvlib.DIM, curses.A_BOLD))
        weeks = calendar.Calendar(0).monthdatescalendar(self.day.year, self.day.month)
        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                y, x = 4 + r, x0 + c * cell
                style = 0 if day.month == self.day.month else A(rvlib.DIM)
                if day == today:
                    style = A(rvlib.ACCENT, curses.A_BOLD)
                if day == self.day:
                    style = A(rvlib.SELECTED, curses.A_BOLD)
                self.put(y, x, f"{day.day:>3}", cell, style)
                if self.on_day(day):
                    self.put(y, x + 3, "•", 1, A(rvlib.WARN))
        # Agenda for the chosen day, beside the grid when there is room.
        side = w >= 80
        ax, ay = (x0 + 7 * cell + 6, 3) if side else (3, 5 + len(weeks) + 1)
        width = w - ax - 3
        self.put(ay, ax, self.day.strftime("%A %-d %B"), width, A(rvlib.TITLE, curses.A_BOLD))
        events = self.on_day(self.day)
        self.pick = max(0, min(self.pick, len(events) - 1))
        if not events:
            self.put(ay + 2, ax, "No events — press a to add one", width, A(rvlib.DIM))
        for i, e in enumerate(events[: max(0, h - ay - 5)]):
            span = f"{e['time']}–{e['end']}" if e.get("end") else (e.get("time") or "all day")
            label = f"{span:>11}  {e.get('title') or '(untitled)'}"
            if e.get("calendar"):
                label += f"  · {e['calendar']}"
            if e.get("repeat", "none") != "none":
                label += f"  ↻ {e['repeat']}"
            self.put(ay + 2 + i, ax, label.ljust(width), width, A(rvlib.SELECTED) if i == self.pick else 0)
            extra = e.get("note") or e.get("location")
            if extra and i == self.pick:
                self.put(ay + 3 + len(events), ax, extra, width, A(rvlib.DIM))
        # Upcoming (next 14 days) under the grid when beside.
        if side:
            uy = 5 + len(weeks) + 1
            self.put(uy, x0, "Next two weeks", w - 6, A(rvlib.ACCENT, curses.A_BOLD))
            line = uy + 1
            for n in range(14):
                d = today + dt.timedelta(days=n)
                for e in self.on_day(d):
                    if line >= h - 3:
                        break
                    when = "today" if n == 0 else "tomorrow" if n == 1 else d.strftime("%a %-d %b")
                    self.put(line, x0, f"{when:<11} {e.get('time') or '':>5}  {e.get('title', '')}", w - 6)
                    line += 1
        self.put(h - 2, 2, "─" * (w - 4), w - 4, A(rvlib.DIM))
        import time
        if self.message and time.monotonic() < self.message_until:
            self.put(h - 1, 2, self.message, w - 4, A(self.message_colour, curses.A_BOLD))
        else:
            self.put(h - 1, 2, self.keys_hint + "  ·  q quit", w - 4, A(rvlib.DIM))
        s.refresh()

    def ask(self, event: dict) -> dict | None:
        title = self.prompt("Title", event.get("title", ""))
        if not title:
            return None
        time_text = self.prompt("Time HH:MM (empty = all day)", event.get("time", ""))
        if time_text is None:
            return None
        time_text = time_text.strip()
        if time_text and not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", time_text):
            self.flash("Time must look like 09:30", rvlib.BAD)
            return None
        if time_text and len(time_text) == 4:
            time_text = "0" + time_text
        repeat = self.choose("Repeat", REPEATS, event.get("repeat", "none")) or "none"
        note = self.prompt("Note (optional)", event.get("note", "")) or ""
        return {**event, "title": title.strip(), "time": time_text, "repeat": repeat, "note": note.strip()}

    def on_key(self, key: int, row) -> None:
        moves = {ord("h"): -1, curses.KEY_LEFT: -1, ord("l"): 1, curses.KEY_RIGHT: 1}
        events = self.on_day(self.day)
        if key in moves:
            self.day += dt.timedelta(days=moves[key])
        elif key in (ord("H"), ord("[")):
            first = self.day.replace(day=1) - dt.timedelta(days=1)
            self.day = first.replace(day=min(self.day.day, calendar.monthrange(first.year, first.month)[1]))
        elif key in (ord("L"), ord("]")):
            nxt = (self.day.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
            self.day = nxt.replace(day=min(self.day.day, calendar.monthrange(nxt.year, nxt.month)[1]))
        elif key == ord("t"):
            self.day = dt.date.today()
        elif key == ord("c"):
            self.manage()
        elif key == ord("S"):
            if not self.sources():
                self.flash("No calendars to sync — press c to add one", rvlib.WARN)
            self.sync()
        elif key == ord("E"):
            if rvlib.have("evolution"):
                rvlib.spawn(["evolution", "--component=calendar"])
                self.flash("Opening Evolution… new events appear here after a sync (S)", rvlib.DIM, 6)
            else:
                self.flash("Evolution is not installed: sudo apt install evolution", rvlib.WARN)
        elif key == ord("J"):
            self.pick += 1
        elif key == ord("K"):
            self.pick = max(0, self.pick - 1)
        elif key == ord("a"):
            event = self.ask({"id": uuid.uuid4().hex[:8], "date": self.day.isoformat()})
            if event:
                self.events.append(event)
                self.save()
                self.flash("Added", rvlib.GOOD)
        elif key in (*rvlib.ENTER, ord("e"), ord("x")) and events and events[self.pick].get("calendar"):
            self.flash(f"From {events[self.pick]['calendar']} — change it there (E opens Evolution)", rvlib.WARN, 6)
        elif key in (*rvlib.ENTER, ord("e")) and events:
            original = events[self.pick]
            event = self.ask(original)
            if event:
                self.events[self.events.index(original)] = event
                self.save()
                self.flash("Saved", rvlib.GOOD)
        elif key == ord("x") and events:
            original = events[self.pick]
            if self.confirm(f"Delete '{original.get('title')}'" + (" (all repeats)" if original.get("repeat", "none") != "none" else "")):
                self.events.remove(original)
                self.save()

    def manage(self) -> None:
        """Add or remove synced calendars (stored in settings → calendar.sources)."""
        while True:
            sources = self.sources()
            status = {r["name"]: r for r in self.sync_report}
            rows = []
            for source in sources:
                r = status.get(source.get("name"))
                state = "" if r is None else (f"{r['count']} events" if r.get("ok") else "error")
                rows.append(f"{source.get('name')}  ({state or 'not synced yet'})")
            add_link, add_file, add_evo = ("+ Add an online calendar (ICS / webcal link)", "+ Add an .ics file",
                                           "+ Add Evolution (its Google, Outlook, CalDAV… accounts)")
            picked = self.choose("Calendars — pick one to remove", rows + [add_link, add_file, add_evo])
            if picked is None:
                return
            if picked in rows:
                source = sources[rows.index(picked)]
                if self.confirm(f"Remove {source.get('name')}"):
                    rvlib.set_setting("calendar.sources", [s for s in sources if s is not source])
                continue
            if picked == add_evo:
                url, name = "evolution", "Evolution"
            elif picked == add_file:
                url = self.prompt("Path to the .ics file")
                if not url:
                    continue
                if not rvlib.expand(url).is_file():
                    self.flash("File not found", rvlib.BAD)
                    continue
                name = self.prompt("Name", rvlib.expand(url).stem) or rvlib.expand(url).stem
            else:
                url = self.prompt("ICS link (Google: Settings → calendar → Secret address in iCal format)")
                if not url:
                    continue
                if not re.match(r"^(https?|webcal)://", url.strip()):
                    self.flash("A link starts with https:// or webcal://", rvlib.BAD)
                    continue
                name = self.prompt("Name", "Online calendar") or "Online calendar"
            if any(s.get("url") == url.strip() for s in sources):
                self.flash("Already added", rvlib.WARN)
                continue
            rvlib.set_setting("calendar.sources", sources + [{"name": name.strip(), "url": url.strip()}])
            self.sync()

    def intercept(self, key: int) -> int | None:
        # j/k and up/down move by week here instead of through a list.
        if key in (ord("j"), curses.KEY_DOWN):
            self.day += dt.timedelta(days=7)
            return None
        if key in (ord("k"), curses.KEY_UP):
            self.day -= dt.timedelta(days=7)
            return None
        return key

if __name__ == "__main__":
    rvlib.guard(CalendarApp().start)
