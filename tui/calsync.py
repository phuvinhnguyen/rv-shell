#!/usr/bin/env python3
"""Calendar sync: read other calendars into rv (read-only).

    calsync.py            sync every source in settings → calendar.sources
    calsync.py --check    sync and print a summary

A source is {"name": "...", "url": "..."} where url is one of
  https://… or webcal://…   an iCalendar (.ics) feed — Google's "secret
                            address in iCal format", Outlook's published ICS
                            link, a shared/public calendar, a school timetable
  /path/to/file.ics or ~/…  a downloaded .ics file (re-read on every sync)
  evolution                 every calendar Evolution knows: its local ones
                            and the accounts added in Evolution (Google,
                            Microsoft 365/Outlook, CalDAV, Exchange…)

Occurrences from 60 days ago to a year ahead are expanded (repeat rules,
exceptions, time zones) into ~/.local/share/rv/calendar-sync.json, which the
bar's clock popup and `rv open calendar` read. Standard library only.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import sys
from configparser import ConfigParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402

OUT = rvlib.DATA_HOME / "calendar-sync.json"
LOCAL_TZ = dt.datetime.now().astimezone().tzinfo
PAST_DAYS, FUTURE_DAYS = 60, 366
WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
# Windows time-zone names that Outlook writes into TZID.
WINDOWS_TZ = {
    "Arabian Standard Time": "Asia/Dubai", "UTC": "UTC", "GMT Standard Time": "Europe/London",
    "W. Europe Standard Time": "Europe/Berlin", "Romance Standard Time": "Europe/Paris",
    "Eastern Standard Time": "America/New_York", "Central Standard Time": "America/Chicago",
    "Pacific Standard Time": "America/Los_Angeles", "SE Asia Standard Time": "Asia/Bangkok",
    "China Standard Time": "Asia/Shanghai", "Tokyo Standard Time": "Asia/Tokyo",
    "India Standard Time": "Asia/Kolkata", "Singapore Standard Time": "Asia/Singapore",
    "AUS Eastern Standard Time": "Australia/Sydney",
}


# --------------------------------------------------------------- iCalendar

def unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def parse_line(line: str) -> tuple[str, dict[str, str], str]:
    # NAME;PARAM=VALUE;PARAM="QUOTED":value
    match = re.match(r'^([A-Za-z0-9-]+)((?:;[^:;=]+=(?:"[^"]*"|[^:;]*))*):(.*)$', line)
    if not match:
        return "", {}, ""
    params = {}
    for part in re.findall(r';([^:;=]+)=("[^"]*"|[^:;]*)', match.group(2)):
        params[part[0].upper()] = part[1].strip('"')
    return match.group(1).upper(), params, match.group(3)


def unescape(value: str) -> str:
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), value)


def components(text: str) -> list[dict]:
    """Every VEVENT as {name: [(params, value), …]}."""
    events, current, depth = [], None, 0
    for line in unfold(text):
        name, params, value = parse_line(line)
        if name == "BEGIN":
            if value.upper() == "VEVENT" and current is None:
                current, depth = {}, 0
            elif current is not None:
                depth += 1  # VALARM etc. inside the event: skip its properties
            continue
        if name == "END":
            if current is not None:
                if value.upper() == "VEVENT" and depth == 0:
                    events.append(current)
                    current = None
                else:
                    depth -= 1
            continue
        if current is not None and depth == 0 and name:
            current.setdefault(name, []).append((params, value))
    return events


def zone(tzid: str | None):
    if not tzid:
        return LOCAL_TZ
    tzid = WINDOWS_TZ.get(tzid, tzid).strip("/")
    for candidate in (tzid, tzid.split("/", 1)[-1] if tzid.count("/") > 1 else tzid):
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return LOCAL_TZ


def when(params: dict[str, str], value: str):
    """A date (all-day) or an aware datetime."""
    value = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return dt.date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    stamp = dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        return stamp.replace(tzinfo=dt.timezone.utc)
    return stamp.replace(tzinfo=zone(params.get("TZID")))


def first(event: dict, name: str):
    values = event.get(name)
    return values[0] if values else ({}, "")


def all_values(event: dict, name: str) -> list:
    out = []
    for params, value in event.get(name, []):
        for part in value.split(","):
            if part.strip():
                out.append(when(params, part))
    return out


def rrule_dates(start, rule: str, window_end):
    """Yield occurrence starts for the RRULE subset calendars actually use."""
    parts = dict(p.split("=", 1) for p in rule.upper().split(";") if "=" in p)
    freq = parts.get("FREQ", "")
    interval = max(1, int(parts.get("INTERVAL", "1") or 1))
    count = int(parts["COUNT"]) if "COUNT" in parts else None
    until = None
    if "UNTIL" in parts:
        until = when({}, parts["UNTIL"])
        if isinstance(start, dt.datetime) and not isinstance(until, dt.datetime):
            until = dt.datetime.combine(until, dt.time(23, 59, 59), start.tzinfo)
        elif isinstance(start, dt.datetime) and until.tzinfo is None:
            until = until.replace(tzinfo=start.tzinfo)
        elif not isinstance(start, dt.datetime) and isinstance(until, dt.datetime):
            until = until.date()
    byday = [d for d in parts.get("BYDAY", "").split(",") if d]
    bymonthday = [int(d) for d in parts.get("BYMONTHDAY", "").split(",") if d]
    bymonth = [int(m) for m in parts.get("BYMONTH", "").split(",") if m]
    day0 = start.date() if isinstance(start, dt.datetime) else start

    def at(day: dt.date):
        return dt.datetime.combine(day, start.timetz()) if isinstance(start, dt.datetime) else day

    def nth_weekday(year: int, month: int, spec: str) -> list[dt.date]:
        m = re.fullmatch(r"([+-]?\d*)(MO|TU|WE|TH|FR|SA|SU)", spec)
        if not m:
            return []
        weekday = WEEKDAYS.index(m.group(2))
        days = [dt.date(year, month, d) for d in range(1, 32) if _valid(year, month, d)
                and dt.date(year, month, d).weekday() == weekday]
        if not m.group(1):
            return days
        n = int(m.group(1))
        index = n - 1 if n > 0 else n          # 2MO → second Monday, -1FR → last Friday
        return [days[index]] if -len(days) <= index < len(days) else []

    produced = 0
    limit_day = window_end.date() if isinstance(window_end, dt.datetime) else window_end
    step = 0
    while step < 5000:
        candidates: list[dt.date] = []
        if freq == "DAILY":
            candidates = [day0 + dt.timedelta(days=step * interval)]
        elif freq == "WEEKLY":
            week_start = day0 - dt.timedelta(days=day0.weekday()) + dt.timedelta(weeks=step * interval)
            days = [WEEKDAYS.index(d[-2:]) for d in byday] or [day0.weekday()]
            candidates = sorted(week_start + dt.timedelta(days=d) for d in days)
        elif freq == "MONTHLY":
            month_index = day0.month - 1 + step * interval
            year, month = day0.year + month_index // 12, month_index % 12 + 1
            if byday:
                candidates = sorted(d for spec in byday for d in nth_weekday(year, month, spec))
            else:
                for d in bymonthday or [day0.day]:
                    if d < 0:
                        d = _month_len(year, month) + d + 1
                    if _valid(year, month, d):
                        candidates.append(dt.date(year, month, d))
        elif freq == "YEARLY":
            year = day0.year + step * interval
            months = bymonth or [day0.month]
            for month in months:
                if byday:
                    candidates += [d for spec in byday for d in nth_weekday(year, month, spec)]
                elif _valid(year, month, day0.day):
                    candidates.append(dt.date(year, month, day0.day))
            candidates.sort()
        else:
            yield start
            return
        for day in candidates:
            if day < day0:
                continue
            occurrence = at(day)
            if until is not None and occurrence > until:
                return
            if count is not None and produced >= count:
                return
            if day > limit_day:
                return
            produced += 1
            yield occurrence
        step += 1


def _month_len(year: int, month: int) -> int:
    return ((dt.date(year + month // 12, month % 12 + 1, 1)) - dt.date(year, month, 1)).days


def _valid(year: int, month: int, day: int) -> bool:
    return 1 <= day <= _month_len(year, month)


def local_parts(value) -> tuple[str, str]:
    if isinstance(value, dt.datetime):
        value = value.astimezone(LOCAL_TZ)
        return value.date().isoformat(), value.strftime("%H:%M")
    return value.isoformat(), ""


def expand(text: str, calendar: str) -> list[dict]:
    today = dt.date.today()
    lo, hi = today - dt.timedelta(days=PAST_DAYS), today + dt.timedelta(days=FUTURE_DAYS)
    events = components(text)
    # RECURRENCE-ID entries replace one occurrence of their series.
    overrides: dict[str, set] = {}
    for event in events:
        if "RECURRENCE-ID" in event:
            uid = first(event, "UID")[1]
            params, value = first(event, "RECURRENCE-ID")
            overrides.setdefault(uid, set()).add(local_parts(when(params, value)))
    out = []
    for event in events:
        if first(event, "STATUS")[1].upper() == "CANCELLED":
            continue
        params, value = first(event, "DTSTART")
        if not value:
            continue
        try:
            start = when(params, value)
        except ValueError:
            continue
        end_params, end_value = first(event, "DTEND")
        duration = None
        try:
            if end_value:
                duration = when(end_params, end_value) - start
        except (ValueError, TypeError):
            duration = None
        title = unescape(first(event, "SUMMARY")[1]) or "(busy)"
        location = unescape(first(event, "LOCATION")[1])
        uid = first(event, "UID")[1]
        try:
            excluded = {local_parts(d) for d in all_values(event, "EXDATE")}
        except ValueError:
            excluded = set()
        rule = first(event, "RRULE")[1]
        is_override = "RECURRENCE-ID" in event
        window_end = dt.datetime.combine(hi, dt.time(23, 59), LOCAL_TZ) if isinstance(start, dt.datetime) else hi
        starts = [start] if not rule or is_override else rrule_dates(start, rule, window_end)
        try:
            extra = all_values(event, "RDATE") if not is_override else []
        except ValueError:
            extra = []
        for occurrence in list(starts) + extra:
            key = local_parts(occurrence)
            if key in excluded or (not is_override and rule and key in overrides.get(uid, set())):
                continue
            day = dt.date.fromisoformat(key[0])
            if not lo <= day <= hi:
                continue
            ends = ""
            if duration is not None and isinstance(occurrence, dt.datetime):
                ends = local_parts(occurrence + duration)[1]
            days = 1
            if duration is not None and not isinstance(occurrence, dt.datetime):
                days = max(1, duration.days)
            for offset in range(min(days, 14)):  # multi-day all-day events
                out.append({"date": (day + dt.timedelta(days=offset)).isoformat(), "time": key[1], "end": ends,
                            "title": title, "location": location, "calendar": calendar})
    return out


# ------------------------------------------------------------------ sources

def fetch(url: str) -> str:
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    request = Request(url, headers={"User-Agent": "rv-calendar/1 (+Debian)"})
    with urlopen(request, timeout=20) as response:
        return response.read(20_000_000).decode(response.headers.get_content_charset() or "utf-8", "replace")


def evolution_calendars() -> list[tuple[str, str]]:
    """(display name, iCalendar text) for every enabled Evolution calendar.

    Evolution keeps a copy of each account's calendar (Google, Microsoft 365,
    CalDAV, Exchange…) in ~/.cache/evolution/calendar/<id>/cache.db and its
    local ones in ~/.local/share/evolution/calendar/<id>/calendar.ics, so
    no Evolution libraries are needed to read them.
    """
    home = Path.home()
    names: dict[str, str] = {}
    sources = home / ".config/evolution/sources"
    for file in sources.glob("*.source") if sources.is_dir() else []:
        parser = ConfigParser(interpolation=None, strict=False)
        try:
            parser.read(file)
        except Exception:
            continue
        if not parser.has_section("Calendar"):
            continue
        if parser.get("Data Source", "Enabled", fallback="true").lower() == "false":
            continue
        names[file.stem] = parser.get("Data Source", "DisplayName", fallback=file.stem)
    found = []
    for uid, name in names.items():
        texts = []
        db = home / ".cache/evolution/calendar" / uid / "cache.db"
        if db.is_file():
            try:
                with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5) as conn:
                    texts = [row[0] for row in conn.execute("SELECT ECacheOBJ FROM ECacheObjects") if row[0]]
            except sqlite3.Error:
                texts = []
        local = home / ".local/share/evolution/calendar" / uid / "calendar.ics"
        if local.is_file():
            texts.append(local.read_text(errors="replace"))
        if texts:
            found.append((name, "\n".join(texts)))
    return found


def sync() -> dict:
    sources = rvlib.settings().get("calendar", {}).get("sources", [])
    events: list[dict] = []
    report = []
    for source in sources if isinstance(sources, list) else []:
        name = str(source.get("name") or source.get("url") or "calendar")
        url = str(source.get("url") or "").strip()
        try:
            if url == "evolution":
                calendars = evolution_calendars()
                if not calendars:
                    raise RuntimeError("no Evolution calendars yet — add an account in Evolution first")
                count = 0
                for cal_name, text in calendars:
                    found = expand(text, cal_name)
                    events += found
                    count += len(found)
            elif url.startswith(("http://", "https://", "webcal://")):
                found = expand(fetch(url), name)
                events += found
                count = len(found)
            else:
                found = expand(rvlib.expand(url).read_text(errors="replace"), name)
                events += found
                count = len(found)
            report.append({"name": name, "ok": True, "count": count})
        except Exception as error:  # one bad source must not stop the others
            report.append({"name": name, "ok": False, "error": str(error)[:200]})
    previous = rvlib.read_json(OUT, {}) or {}
    if report and not any(r["ok"] for r in report) and previous.get("events"):
        events = previous["events"]  # offline: keep the last good copy
    seen, unique = set(), []
    for e in sorted(events, key=lambda e: (e["date"], e["time"], e["title"])):
        key = (e["date"], e["time"], e["title"], e["calendar"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    result = {"updated": dt.datetime.now().isoformat(timespec="seconds"), "sources": report, "events": unique}
    rvlib.write_json(OUT, result)
    return result


def main(argv: list[str]) -> int:
    result = sync()
    if "--check" in argv:
        for r in result["sources"]:
            print(f"{'ok ' if r['ok'] else 'ERR'} {r['name']}: " + (f"{r['count']} events" if r["ok"] else r["error"]))
        if not result["sources"]:
            print("No calendars configured: add one in `rv open calendar` (press c)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
