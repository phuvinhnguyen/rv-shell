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

    function on(d) {
        return events.filter(ev => occursOn(ev, d))
                     .concat(synced[iso(d)] || [])
                     .sort((a, b) => (a.time || "").localeCompare(b.time || ""));
    }

    // [{date, event}] for the next `days` days, today first.
    function upcoming(days) {
        const out = [];
        const today = new Date();
        for (let i = 0; i < days; i++) {
            const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() + i);
            for (const ev of on(d)) out.push({ date: d, event: ev });
        }
        return out;
    }
}
