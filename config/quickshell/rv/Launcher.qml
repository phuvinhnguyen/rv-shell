pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Launcher state and search. The window (LauncherWindow) only exists while
// open; this singleton keeps the small bits that should survive between
// openings (frecency counts) and runs the searches.
//
// Modes and prefixes, typed in the search field:
//   apps       applications and utilities (default)
//   ;  tools   utilities only: rv's terminal apps and your own tools
//   :  clip    clipboard history (Super+V)
//   >  run     a shell command (Enter: in the background, Shift+Enter: in a terminal)
//   =  calc    arithmetic; Enter copies the result
//   ?  web     Enter searches DuckDuckGo: a quick answer, then pages; Enter on
//              one opens it in the browser (Shift+Enter: the full results page)
Singleton {
    id: root

    property bool open: false
    property string mode: "apps"
    property string query: ""
    property int selected: 0
    readonly property var modes: ["apps", "tools", "clipboard", "run", "web"]

    function toggle(m) {
        if (open && (m === undefined || m === mode)) { open = false; return; }
        show(m || "apps");
    }
    function show(m, keepQuery) {
        mode = modes.includes(m) ? m : "apps";
        if (!keepQuery) query = "";
        selected = 0;
        if (mode === "clipboard") clipProc.running = true;
        toolsProc.running = true;
        open = true;
    }
    // Tab keeps what was typed, so "foo" → Tab → … → web searches "foo".
    function cycle(step) {
        const i = (modes.indexOf(effectiveMode) + step + modes.length) % modes.length;
        query = text;
        show(modes[i], true);
    }

    // ---- data ------------------------------------------------------------------
    property var tools: []
    property var clips: []
    property var counts: ({})

    Process {
        id: toolsProc
        command: [Config.rv, "tools", "--json"]
        stdout: StdioCollector {
            onStreamFinished: { try { root.tools = JSON.parse(text); } catch (e) { root.tools = []; } }
        }
    }
    Process {
        id: clipProc
        command: ["cliphist", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                root.clips = text.split("\n").filter(l => l.includes("\t")).slice(0, 200).map(l => {
                    const tab = l.indexOf("\t");
                    return { id: l.slice(0, tab), text: l.slice(tab + 1) };
                });
            }
        }
    }
    FileView {
        id: frecency
        path: Config.dataHome + "/launcher.json"
        printErrors: false
        onLoaded: { try { root.counts = JSON.parse(text()).counts || {}; } catch (e) { root.counts = {}; } }
    }
    function remember(key) {
        const c = Object.assign({}, counts);
        c[key] = (c[key] || 0) + 1;
        counts = c;
        Quickshell.execDetached(["sh", "-c", 'mkdir -p "$1" && printf %s "$2" > "$1/launcher.json"', "sh",
                                 Config.dataHome, JSON.stringify({ counts: c })]);
    }

    // ---- web search ------------------------------------------------------------------
    // Runs only on Enter (searching on every pause would trip DuckDuckGo's
    // rate limit). Results stay until the text changes.
    property string webQuery: ""
    property var webResults: []
    property bool webBusy: false
    readonly property string searchEngine: Config.get("launcher", "searchEngine", "https://duckduckgo.com/?q={query}")

    function searchUrl(q) { return searchEngine.replace("{query}", encodeURIComponent(q)); }
    function webSearch(q) {
        q = q.trim();
        if (!q) return;
        webQuery = q;
        webResults = [];
        webBusy = true;
        selected = 0;
        webProc.running = false;
        webProc.command = ["python3", Config.repo + "/tui/websearch.py", q];
        webProc.running = true;
    }
    function openUrl(url) { Quickshell.execDetached(["xdg-open", url]); }

    Process {
        id: webProc
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.webResults = JSON.parse(text); } catch (e) { root.webResults = []; }
                root.webBusy = false;
                root.selected = 0;
            }
        }
        onExited: root.webBusy = false
    }

    // Helper entries that only duplicate another app.
    readonly property var hidden: ["org.codeberg.dnkl.footclient", "org.codeberg.dnkl.foot-server", "footclient", "foot-server"]

    // ---- matching ----------------------------------------------------------------
    // Subsequence match with bonuses for word starts and contiguous runs.
    function score(needle, hay) {
        if (!needle) return 1;
        hay = (hay || "").toLowerCase();
        const exact = hay.indexOf(needle);
        if (exact === 0) return 1000 - hay.length;
        if (exact > 0) return 700 - exact - hay.length / 10 + (/[\s\-_.]/.test(hay[exact - 1]) ? 150 : 0);
        let s = 0, j = 0, run = 0;
        for (let i = 0; i < hay.length && j < needle.length; i++) {
            if (hay[i] === needle[j]) {
                run++; j++;
                s += 10 + run * 5 + ((i === 0 || /[\s\-_.]/.test(hay[i - 1])) ? 20 : 0);
            } else run = 0;
        }
        return j === needle.length ? s : 0;
    }

    readonly property string effectiveMode: {
        const q = query;
        if (q.startsWith("=")) return "calc";
        if (q.startsWith(">")) return "run";
        if (q.startsWith(";")) return "tools";
        if (q.startsWith(":")) return "clipboard";
        if (q.startsWith("?")) return "web";
        return mode;
    }
    // What was typed, without a mode prefix ("?rust" → "rust"; in Run mode
    // picked from the chips, "ls" stays "ls").
    readonly property string text: /^[=>;:?]/.test(query) ? query.slice(1) : query
    readonly property string needle: text.trim().toLowerCase()

    onEffectiveModeChanged: if (effectiveMode === "clipboard" && clips.length === 0) clipProc.running = true

    function calc(expr) {
        const allowed = /^[\d\s+\-*/%^().,]*$|^(?:[\d\s+\-*/%^().,]|sqrt|sin|cos|tan|log|ln|exp|pi|abs|pow|floor|ceil|round|min|max|e)*$/i;
        if (!expr.trim() || !allowed.test(expr)) return null;
        try {
            const js = expr.replace(/\^/g, "**").replace(/\bln\b/g, "log").replace(/\bpi\b/gi, "PI").replace(/\be\b/g, "E");
            const value = Function("with (Math) { return (" + js + "); }")();
            if (typeof value !== "number" || !isFinite(value)) return null;
            return String(Math.round(value * 1e10) / 1e10);
        } catch (e) { return null; }
    }

    // Nothing is indexed while closed: desktop entries load on first open.
    readonly property var results: {
        if (!open) return [];
        const n = needle;
        const out = [];
        const m = effectiveMode;
        if (m === "calc") {
            const v = calc(text);
            if (v !== null) out.push({ kind: "calc", title: v, subtitle: "Enter copies the result", glyph: Icons.calculator, value: v });
            return out;
        }
        if (m === "run") {
            const cmd = text.trim();
            if (cmd) out.push({ kind: "run", title: cmd, subtitle: "Enter: run · Shift+Enter: run in a terminal", glyph: Icons.terminal, value: cmd });
            return out;
        }
        if (m === "web") {
            const q = text.trim();
            if (!q) return out;
            if (q !== webQuery) {
                out.push({ kind: "websearch", title: `Search the web for “${q}”`, subtitle: "Enter: search here · Shift+Enter: open in the browser",
                           glyph: Icons.web, value: q });
                return out;
            }
            if (webBusy) {
                out.push({ kind: "busy", title: `Searching for “${q}”…`, subtitle: "DuckDuckGo", glyph: Icons.web, value: q });
                return out;
            }
            for (const r of webResults) {
                let host = "";
                try { host = r.url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0]; } catch (e) {}
                out.push(r.kind === "answer"
                    ? { kind: "answer", title: r.title, subtitle: r.snippet, glyph: Icons.answer, value: r.url, host: host }
                    : { kind: "url", title: r.title, subtitle: host + (r.snippet ? "  ·  " + r.snippet : ""), glyph: Icons.web, value: r.url });
            }
            out.push({ kind: "url", title: webResults.length ? "All results in the browser" : "No results here — open the search in the browser",
                       subtitle: searchUrl(q), glyph: Icons.openExternal, value: searchUrl(q) });
            return out;
        }
        if (m === "clipboard") {
            for (const c of clips) {
                const s = score(n, c.text);
                if (s > 0) out.push({ kind: "clip", title: c.text.startsWith("[[ binary data")
                                      ? "Image " + c.text.replace(/^\[\[ binary data |\]\]$/g, "") : c.text,
                                      subtitle: "", glyph: Icons.clipboard, value: c.id, score: s });
            }
            return n ? out.sort((a, b) => b.score - a.score) : out;
        }
        for (const t of tools) {
            const s = Math.max(score(n, t.name), score(n, t.keywords || "") * 0.6, score(n, t.description) * 0.3);
            if (s > 0) out.push({ kind: "tool", title: t.name, subtitle: t.description, glyph: t.icon || Icons.tools,
                                  value: t.id, score: s + (counts["tool:" + t.id] || 0) * 15 - (m === "apps" ? 60 : 0) });
        }
        if (m === "apps") {
            for (const a of DesktopEntries.applications.values) {
                if (a.noDisplay || hidden.includes(a.id)) continue;
                const s = Math.max(score(n, a.name), score(n, a.genericName) * 0.7,
                                   score(n, (a.keywords || []).join(" ")) * 0.5, score(n, a.comment) * 0.2);
                if (s > 0) out.push({ kind: "app", title: a.name, subtitle: a.genericName || a.comment, icon: a.icon,
                                      value: a, score: s + (counts["app:" + a.id] || 0) * 15 });
            }
        }
        out.sort((a, b) => b.score - a.score || a.title.localeCompare(b.title));
        const top = out.slice(0, 60);
        // Always offer the web as the last resort.
        if (m === "apps" && n)
            top.push({ kind: "websearch", title: `Search the web for “${text.trim()}”`, subtitle: "Enter: results here · Shift+Enter: open in the browser",
                       glyph: Icons.web, value: text.trim() });
        return top;
    }

    // ---- actions -------------------------------------------------------------------
    function activate(index, alternate) {
        const r = results[index];
        if (!r) return;
        if (r.kind === "busy") return;
        if (r.kind === "websearch") {
            if (alternate) { open = false; openUrl(searchUrl(r.value)); return; }
            if (effectiveMode !== "web") { mode = "web"; query = r.value; }
            webSearch(r.value);
            return;
        }
        open = false;
        switch (r.kind) {
        case "answer":
        case "url":
            openUrl(alternate ? searchUrl(text) : r.value);
            break;
        case "app":
            remember("app:" + r.value.id);
            if (r.value.runInTerminal)
                Quickshell.execDetached([Config.rv, "term", "--"].concat(r.value.command));
            else
                r.value.execute();
            break;
        case "tool":
            remember("tool:" + r.value);
            Quickshell.execDetached([Config.rv, "tool", r.value]);
            break;
        case "clip":
            Quickshell.execDetached(["sh", "-c", 'cliphist decode "$1" | wl-copy', "sh", r.value]);
            break;
        case "calc":
            Quickshell.execDetached(["wl-copy", r.value]);
            break;
        case "run":
            if (alternate) Quickshell.execDetached([Config.rv, "term", "--hold", "--", "sh", "-c", r.value]);
            else Quickshell.execDetached(["sh", "-c", r.value]);
            break;
        }
    }

    function remove(index) {
        const r = results[index];
        if (!r || r.kind !== "clip") return;
        Quickshell.execDetached(["sh", "-c", 'cliphist list | grep -m1 "^$1	" | cliphist delete', "sh", r.value]);
        clips = clips.filter(c => c.id !== r.value);
    }
}
