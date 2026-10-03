pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Settings shared with Hyprland and the terminal apps: the repository's
// defaults.json overlaid with ~/.config/rv/settings.json. The file is
// watched, so `rv settings` changes the running bar immediately.
Singleton {
    id: root

    readonly property string repo: Quickshell.env("RV_REPO") || Qt.resolvedUrl("../../..").toString().replace("file://", "").replace(/\/$/, "")
    readonly property string rv: repo + "/bin/rv"
    readonly property string configHome: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/rv"
    readonly property string dataHome: (Quickshell.env("XDG_DATA_HOME") || Quickshell.env("HOME") + "/.local/share") + "/rv"

    property var defaults: ({})
    property var user: ({})
    readonly property var s: merge(defaults, user)

    function merge(base, over) {
        const out = {};
        for (const key in base) {
            const b = base[key], o = over ? over[key] : undefined;
            if (b !== null && typeof b === "object" && !Array.isArray(b))
                out[key] = merge(b, (o !== null && typeof o === "object") ? o : {});
            else
                out[key] = (o !== undefined && o !== null && typeof o === typeof b) ? o : b;
        }
        return out;
    }
    function parse(text) {
        try { return JSON.parse(text) || {}; } catch (e) { return {}; }
    }
    function get(section, key, fallback) {
        const part = s[section];
        return (part && part[key] !== undefined) ? part[key] : fallback;
    }

    FileView {
        path: root.repo + "/config/rv/defaults.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.defaults = root.parse(text())
    }
    FileView {
        path: root.configHome + "/settings.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.user = root.parse(text())
        onLoadFailed: root.user = ({})
    }

    // ---- Theme -------------------------------------------------------------
    readonly property color accent: get("theme", "accent", "#c2c1ff")
    readonly property color bg: get("theme", "background", "#131317")
    readonly property color surface: get("theme", "surface", "#201f27")
    readonly property color text: get("theme", "text", "#e5e1e7")
    readonly property color muted: get("theme", "muted", "#8e8b97")
    readonly property color good: get("theme", "good", "#83d6a2")
    readonly property color warn: get("theme", "warn", "#f0c674")
    readonly property color bad: get("theme", "bad", "#ff7185")
    readonly property real opacity: get("theme", "opacity", 0.94)
    readonly property int rounding: get("theme", "rounding", 12)
    readonly property string font: get("theme", "font", "Hack Nerd Font")
    readonly property int fontSize: get("theme", "fontSize", 12)

    readonly property color panel: Qt.rgba(bg.r, bg.g, bg.b, opacity)
    readonly property color hover: Qt.rgba(text.r, text.g, text.b, 0.08)
    readonly property color line: Qt.rgba(text.r, text.g, text.b, 0.07)

    function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a); }

    // ---- Bar -----------------------------------------------------------------
    readonly property int barWidth: get("bar", "width", 44)
    property bool barVisible: true

    function run(args) { Quickshell.execDetached([root.rv].concat(args)); }
}
