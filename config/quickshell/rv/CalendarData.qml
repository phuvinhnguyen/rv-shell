pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Your own events (~/.local/share/rv/calendar.json, from `rv open calendar`)
// plus synced read-only ones (calendar-sync.json, from tui/calsync.py:
// Google/Outlook/ICS feeds, .ics files, Evolution).
Singleton {
    id: root

    property var events: []
    property var synced: ({})      // "YYYY-MM-DD" → [event]

    // Re-sync now and then while calendars are configured.
    readonly property var sources: Config.get("calendar", "sources", [])
    Timer {
        interval: Math.max(5, Config.get("calendar", "syncMinutes", 30)) * 60000
        running: root.sources.length > 0
        repeat: true
        triggeredOnStart: true
        onTriggered: Quickshell.execDetached(["python3", Config.repo + "/tui/calsync.py"])
    }
    FileView {
        path: Config.dataHome + "/calendar-sync.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            const byDay = {};
            try {
                for (const ev of (JSON.parse(text()) || {}).events || [])
                    (byDay[ev.date] = byDay[ev.date] || []).push(ev);
            } catch (e) {}
            root.synced = byDay;
        }
        onLoadFailed: root.synced = ({})
    }

    FileView {
        path: Config.dataHome + "/calendar.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            try { root.events = (JSON.parse(text()) || {}).events || []; }
            catch (e) { root.events = []; }
        }
        onLoadFailed: root.events = []
    }

    function iso(d) {
        const p = n => (n < 10 ? "0" : "") + n;
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
    }

    function occursOn(ev, d) {
        const parts = (ev.date || "").split("-").map(Number);
        if (parts.length !== 3) return false;
        const start = new Date(parts[0], parts[1] - 1, parts[2]);
        if (d < start) return false;
        switch (ev.repeat) {
        case "daily": return true;
        case "weekly": return d.getDay() === start.getDay();
        case "monthly": return d.getDate() === start.getDate();
        case "yearly": return d.getDate() === start.getDate() && d.getMonth() === start.getMonth();
        default: return iso(d) === ev.date;
        }
    }

    // Minutes since midnight for "HH:MM" (all-day events count as 0).
    function minutes(t) {
        const m = /^(\d{1,2}):(\d{2})/.exec(t || "");
        return m ? Number(m[1]) * 60 + Number(m[2]) : 0;
    }
    // "past", "now" or "next" relative to the clock; only today's timed
    // events can be past or ongoing. An event without an end lasts an hour.
    function state(ev, d, now) {
        if (!now || iso(d) !== iso(now) || !ev.time) return "next";
        const t = now.getHours() * 60 + now.getMinutes();
        const start = minutes(ev.time);
        const end = ev.end ? minutes(ev.end) : start + 60;
        return t >= (end > start ? end : start + 60) ? "past" : t >= start ? "now" : "next";
    }

    // A day's events in time order; for today, finished ones sink to the end.
    function on(d, now) {
        const rank = ev => state(ev, d, now) === "past" ? 1 : 0;
        return events.filter(ev => occursOn(ev, d))
                     .concat(synced[iso(d)] || [])
                     .sort((a, b) => rank(a) - rank(b) || minutes(a.time) - minutes(b.time)
                                     || (a.time ? 1 : 0) - (b.time ? 1 : 0));
    }

    // [{date, event, state}] for the next `days` days; today's finished events are left out.
    function upcoming(days, now) {
        const out = [];
        const today = now || new Date();
        for (let i = 0; i < days; i++) {
            const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() + i);
            for (const ev of on(d, today)) {
                const st = state(ev, d, today);
                if (st !== "past") out.push({ date: d, event: ev, state: st });
            }
        }
        return out;
    }
}
