#!/usr/bin/env python3
"""rv settings: everything in ~/.config/rv/settings.json, plus links to the
other terminal apps. Bar and theme changes apply live; window and input
changes reload Hyprland automatically.

Keys: Tab/Shift+Tab section · j/k move · h/l or ←/→ change · Enter edit/open
      d reset to default · q quit
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402
import wallpaper  # noqa: E402
from rvlib import Row  # noqa: E402

# (key, label, kind, spec, help). kind: bool | int | float | choice | text | colour
SECTIONS: dict[str, list[tuple]] = {
    "Bar": [
        ("bar.width", "Width", "int", (34, 72, 2), "Bar width in pixels"),
        ("bar.allMonitors", "Show on every monitor", "bool", None, "Off: only the first monitor"),
        ("bar.workspaces", "Workspaces always shown", "int", (1, 10, 1), "More appear when in use"),
        ("bar.clock24h", "24-hour clock", "bool", None, ""),
        ("bar.showDate", "Show date", "bool", None, ""),
        ("bar.showStats", "CPU / memory rings", "bool", None, "Polls /proc every 3 s while shown"),
        ("bar.showMedia", "Media button", "bool", None, "Appears while a player runs"),
        ("bar.showTray", "System tray", "bool", None, ""),
        ("bar.showBattery", "Battery", "bool", None, "Hidden automatically without a battery"),
        ("notifications.timeoutSeconds", "Notification timeout", "int", (2, 30, 1), "Seconds a popup stays"),
        ("notifications.doNotDisturb", "Do not disturb", "bool", None, "Only critical popups"),
    ],
    "Theme": [
        ("@preset", "Apply a colour preset…", "action", None, "Sets accent and background colours"),
        ("theme.accent", "Accent", "colour", None, "Active workspace, highlights, borders"),
        ("theme.background", "Background", "colour", None, "Bar, popups and empty desktop"),
        ("theme.surface", "Surface", "colour", None, "Cards and fields"),
        ("theme.text", "Text", "colour", None, ""),
        ("theme.muted", "Muted text", "colour", None, ""),
        ("theme.opacity", "Panel opacity", "float", (0.5, 1.0, 0.02), "1.0 is solid"),
        ("theme.rounding", "Corner radius", "int", (0, 24, 1), "Shell surfaces"),
        ("theme.font", "Font", "text", None, "Needs Nerd Font glyphs for icons"),
        ("theme.fontSize", "Font size", "int", (9, 18, 1), ""),
        ("@wallpaper", "Choose wallpaper…", "action", None, "Images in ~/Pictures and the repository"),
        ("wallpaper.path", "Wallpaper file", "text", None, "Empty = plain background colour (lightest)"),
        ("wallpaper.fill", "Wallpaper fit", "choice", ["crop", "fit"], ""),
    ],
    "Windows": [
        ("hypr.layout", "Layout", "choice", ["scrolling", "dwindle", "master"], "Scrolling: columns side by side"),
        ("hypr.gapsIn", "Gaps between windows", "int", (0, 30, 1), ""),
        ("hypr.gapsOut", "Gaps at screen edges", "int", (0, 40, 1), ""),
        ("hypr.border", "Border width", "int", (0, 6, 1), ""),
        ("hypr.rounding", "Window corner radius", "int", (0, 24, 1), ""),
        ("hypr.animations", "Animations", "bool", None, ""),
        ("hypr.blur", "Blur", "bool", None, "Costs GPU time and memory"),
        ("hypr.shadow", "Shadows", "bool", None, "Costs GPU time"),
        ("hypr.nightLight", "Warm screen (gammastep)", "bool", None, "Applies at next login"),
    ],
    "Input": [
        ("hypr.kbLayout", "Keyboard layout", "text", None, "e.g. us, us,vn, de"),
        ("hypr.kbOptions", "Keyboard options", "text", None, "e.g. grp:alt_shift_toggle,caps:escape"),
        ("hypr.repeatRate", "Key repeat rate", "int", (10, 80, 5), "Per second"),
        ("hypr.repeatDelay", "Key repeat delay", "int", (150, 800, 25), "Milliseconds"),
        ("hypr.naturalScroll", "Natural touchpad scrolling", "bool", None, ""),
        ("hypr.sensitivity", "Pointer speed", "float", (-1.0, 1.0, 0.1), "-1 slow … 1 fast"),
    ],
    "Idle": [
        ("idle.lockMinutes", "Lock after", "int", (0, 120, 1), "Minutes idle; 0 = never"),
        ("idle.screenOffMinutes", "Screen off after", "int", (0, 120, 1), "Minutes idle; 0 = never"),
        ("idle.suspendMinutes", "Suspend after", "int", (0, 240, 5), "Minutes idle; 0 = never"),
    ],
    "Apps": [
        ("apps.terminal", "Terminal", "text", None, "foot uses one shared server process"),
        ("apps.browser", "Browser", "text", None, "auto = system default browser"),
        ("apps.editor", "Editor", "text", None, "Terminal editors open in the terminal"),
        ("apps.files", "File manager", "text", None, "auto = yazi, nnn, ranger or mc"),
        ("launcher.searchEngine", "Web search in browser", "text", None, "{query} is replaced; Shift+Enter in web search"),
        ("launcher.webResults", "Web results in launcher", "int", (1, 10, 1), "Pages listed under the quick answer"),
        ("launcher.webLocale", "Web search region", "text", None, "DuckDuckGo region, e.g. wt-wt (none), vn-vi, us-en"),
        ("shell.renderer", "Shell renderer", "choice", ["software", "auto"], "software: least memory · restart the bar"),
    ],
    "More": [
        ("@open:wifi", "Wi-Fi", "open", None, ""),
        ("@open:bluetooth", "Bluetooth", "open", None, ""),
        ("@open:display", "Displays", "open", None, "Super+P"),
        ("@open:audio", "Audio", "open", None, ""),
        ("@open:calendar", "Calendar", "open", None, ""),
        ("@open:keys", "Keybindings", "open", None, "Super+/"),
        ("@open:tools", "Utilities", "open", None, "Your own tools live in ~/.config/rv/tools"),
        ("@custom", "Edit custom Hyprland config", "action", None, "~/.config/rv/custom.lua, loaded last"),
        ("@restart", "Restart the bar", "action", None, ""),
        ("@reload", "Reload Hyprland", "action", None, ""),
    ],
}

PRESETS = {
    "Raven (default)": dict(accent="#c2c1ff", background="#131317", surface="#201f27", text="#e5e1e7", muted="#8e8b97"),
    "Nord": dict(accent="#88c0d0", background="#2e3440", surface="#3b4252", text="#eceff4", muted="#8a93a6"),
    "Gruvbox": dict(accent="#d8a657", background="#1d2021", surface="#282828", text="#ebdbb2", muted="#928374"),
    "Catppuccin Mocha": dict(accent="#cba6f7", background="#1e1e2e", surface="#313244", text="#cdd6f4", muted="#9399b2"),
    "Rosé Pine": dict(accent="#ebbcba", background="#191724", surface="#26233a", text="#e0def4", muted="#908caa"),
    "Tokyo Night": dict(accent="#7aa2f7", background="#1a1b26", surface="#24283b", text="#c0caf5", muted="#787c99"),
    "Everforest": dict(accent="#a7c080", background="#232a2e", surface="#2d353b", text="#d3c6aa", muted="#859289"),
    "Mono": dict(accent="#e4e4e7", background="#101012", surface="#1c1c20", text="#f4f4f5", muted="#8b8b93"),
}


class SettingsApp(rvlib.App):
    title = "Settings"
    tabs = list(SECTIONS)
    interval = 0.4
    keys_hint = "Tab section · h/l change · Enter edit · d default"

    def __init__(self) -> None:
        super().__init__()
        self.values: dict = {}
        self.hypr_dirty = 0.0

    def refresh(self) -> None:
        self.values = rvlib.settings()
        if self.hypr_dirty and time.monotonic() - self.hypr_dirty > 0.6:
            self.hypr_dirty = 0.0
            status, out = rvlib.run(["hyprctl", "reload"])
            self.flash("Hyprland reloaded" if status == 0 else f"Reload failed: {out}",
                       rvlib.GOOD if status == 0 else rvlib.BAD)

    def value(self, key: str):
        try:
            return rvlib.lookup(self.values, key)
        except (KeyError, TypeError):
            return None

    def show(self, kind: str, value, spec) -> str:
        if kind == "bool":
            return "● on" if value else "○ off"
        if kind == "float":
            return f"{value:.2f}"
        if kind == "colour":
            return f"■ {value}"
        if kind in ("action", "open"):
            return "›"
        if value in ("", None):
            return "—"
        return str(value)

    def rows(self) -> list[Row]:
        out = []
        for key, label, kind, spec, hint in SECTIONS[self.tabs[self.tab]]:
            value = self.value(key) if not key.startswith("@") else None
            changed = not key.startswith("@") and value != self.default(key)
            out.append(Row(label + (" *" if changed else ""), self.show(kind, value, spec),
                           data=(key, kind, spec), hint=hint, colour=rvlib.ACCENT if changed else 0))
        return out

    def default(self, key: str):
        try:
            return rvlib.lookup(rvlib.defaults(), key)
        except (KeyError, TypeError):
            return None

    def detail(self, row: Row | None) -> list[str]:
        if row is None:
            return []
        key = row.data[0]
        lines = [row.hint] if row.hint else []
        if not key.startswith("@"):
            lines.append(f"{key}   default: {self.default(key)}")
        return lines

    def store(self, key: str, value) -> None:
        rvlib.set_setting(key, value)
        self.values = rvlib.settings()
        if key.startswith("hypr."):
            self.hypr_dirty = time.monotonic()
        if key == "shell.renderer":
            rvlib.rv("restart")
        self.flash(f"Saved {key}", rvlib.GOOD, 1.5)

    def step(self, key: str, kind: str, spec, direction: int) -> None:
        value = self.value(key)
        if kind == "bool":
            self.store(key, not value)
        elif kind in ("int", "float"):
            low, high, step = spec
            new = min(high, max(low, value + direction * step))
            self.store(key, round(new, 2) if kind == "float" else int(new))
        elif kind == "choice":
            index = (spec.index(value) if value in spec else 0) + direction
            self.store(key, spec[index % len(spec)])

    def edit(self, key: str, kind: str, spec) -> None:
        value = self.value(key)
        if kind == "bool":
            self.step(key, kind, spec, 1)
            return
        if kind == "choice":
            picked = self.choose(key, spec, value)
            if picked is not None:
                self.store(key, picked)
            return
        text = self.prompt(key, "" if value is None else str(value))
        if text is None:
            return
        text = text.strip()
        try:
            if kind == "int":
                low, high, _ = spec
                number = int(text)
                if not low <= number <= high:
                    raise ValueError(f"between {low} and {high}")
                self.store(key, number)
            elif kind == "float":
                low, high, _ = spec
                number = float(text)
                if not low <= number <= high:
                    raise ValueError(f"between {low} and {high}")
                self.store(key, number)
            elif kind == "colour":
                if not re.fullmatch(r"#?[0-9a-fA-F]{6}", text):
                    raise ValueError("use #rrggbb")
                self.store(key, "#" + text.lstrip("#").lower())
            else:
                if key == "wallpaper.path" and text and not wallpaper.is_image(rvlib.expand(text)):
                    raise ValueError("not a JPEG/PNG/WebP picture (a Git LFS stub? run: rv wallpaper fetch)")
                self.store(key, text)
        except ValueError as error:
            self.flash(f"Not saved: {error}", rvlib.BAD)

    def action(self, key: str) -> None:
        if key == "@preset":
            name = self.choose("Colour preset", list(PRESETS))
            if name:
                for field, colour in PRESETS[name].items():
                    rvlib.set_setting(f"theme.{field}", colour)
                self.store("hypr.border", self.value("hypr.border"))  # reload borders too
                self.flash(f"Applied {name}", rvlib.GOOD)
        elif key == "@wallpaper":
            images = wallpapers()
            if not images:
                self.flash("No pictures yet — run `rv wallpaper fetch` or copy some into ~/Pictures/WallPapers", rvlib.WARN, 8)
                return
            names = ["(none: plain colour)"] + [str(p).replace(str(Path.home()), "~") for p in images]
            picked = self.choose("Wallpaper", names, self.value("wallpaper.path"))
            if picked:
                self.store("wallpaper.path", "" if picked.startswith("(none") else picked)
        elif key.startswith("@open:"):
            rvlib.rv("open", key.split(":", 1)[1])
        elif key == "@custom":
            path = rvlib.CONFIG_HOME / "custom.lua"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(CUSTOM_TEMPLATE)
            editor = self.value("apps.editor")
            if editor in ("auto", "") or rvlib.is_gui(editor):
                editor = os.environ.get("EDITOR", "vim")
            import curses
            curses.endwin()
            subprocess.call([*editor.split(), str(path)])
            self.hypr_dirty = time.monotonic()
        elif key == "@restart":
            rvlib.rv("restart")
            self.flash("Restarting the bar…", rvlib.GOOD)
        elif key == "@reload":
            self.hypr_dirty = time.monotonic() - 1

    def on_key(self, key: int, row: Row | None) -> None:
        if row is None:
            return
        name, kind, spec = row.data
        if key in rvlib.ENTER or key == ord(" "):
            if kind == "action":
                self.action(name)
            elif kind == "open":
                self.action(name)
            else:
                self.edit(name, kind, spec)
        elif key in rvlib.LEFT and kind in ("bool", "int", "float", "choice"):
            self.step(name, kind, spec, -1)
        elif key in rvlib.RIGHT and kind in ("bool", "int", "float", "choice"):
            self.step(name, kind, spec, 1)
        elif key == ord("d") and not name.startswith("@"):
            self.store(name, self.default(name))


def wallpapers() -> list[Path]:
    return wallpaper.pictures()[:300]


CUSTOM_TEMPLATE = """-- Your own Hyprland additions. Loaded after everything else, so anything
-- here wins. `ctx.prefs` holds the merged settings; `ctx.rv` is the rv command.
-- Saving from `rv settings` reloads Hyprland; otherwise run `hyprctl reload`.
return function(ctx)
    -- hl.bind("SUPER + M", hl.dsp.exec_cmd("foot -e cmus"), { description = "Music" })
    -- hl.window_rule({ match = { class = "^steam$" }, float = true })
    -- hl.monitor({ output = "HDMI-A-1", mode = "1920x1080@60", position = "auto-right", scale = 1 })
end
"""


if __name__ == "__main__":
    rvlib.guard(SettingsApp().start)
