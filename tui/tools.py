#!/usr/bin/env python3
"""Utilities: rv's built-in actions plus your own tools.

    tools.py list [--json]    what the launcher shows (Super+Shift+A)
    tools.py run ID           run one
    tools.py                  terminal picker (`rv open tools`)

Your own tools live in any folder listed in settings → tools.paths
(default ~/.config/rv/tools) and in the repository's tools/ folder.
Three shapes are understood:

1. A single executable script. Optional header comments describe it:
       #!/bin/sh
       # name: Weather
       # icon: 󰖐
       # description: Today's forecast
       # terminal: hold          (no | yes | hold — keep the window open)
       # keywords: forecast rain
2. A folder with tool.json:
       {"name": "...", "icon": "...", "description": "...",
        "exec": "run.sh", "terminal": "hold", "keywords": "..."}
   `exec` is relative to the folder (or any command on PATH).
3. A raven-shell tool folder (tool.json with "label" + gui.sh). Each of its
   actions becomes an entry; the JSON reply is shown as a notification.
"""

from __future__ import annotations

import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402

RV = str(rvlib.REPO / "bin" / "rv")

# (id, name, glyph, description, command, keywords)
BUILTINS: list[tuple[str, str, str, str, list[str], str]] = [
    ("settings", "Settings", "\U000f0493", "Bar, theme, windows, input, idle, apps", [RV, "open", "settings"], "preferences config"),
    ("wifi", "Wi-Fi", "\U000f0928", "Scan, connect and forget networks", [RV, "open", "wifi"], "network wireless internet"),
    ("bluetooth", "Bluetooth", "\U000f00af", "Pair and connect devices", [RV, "open", "bluetooth"], "headphones pair"),
    ("display", "Displays", "\U000f0379", "Resolution, scale, layout of monitors", [RV, "open", "display"], "monitor screen resolution projector"),
    ("audio", "Audio", "\U000f057e", "Volume, outputs, inputs and apps", [RV, "open", "audio"], "sound volume speaker microphone"),
    ("calendar", "Calendar", "\U000f00ed", "Month view and events", [RV, "open", "calendar"], "events agenda date"),
    ("keys", "Keybindings", "\U000f030c", "Every Hyprland shortcut", [RV, "open", "keys"], "shortcuts cheatsheet help"),
    ("emoji", "Emoji", "\U000f01f2", "Search and copy an emoji", [RV, "open", "emoji"], "smiley unicode"),
    ("monitor", "System monitor", "\U000f061a", "Processes, CPU and memory", [RV, "app", "monitor"], "htop btop task manager"),
    ("clipboard", "Clipboard history", "\U000f0a38", "Super+V", [RV, "launcher", "clipboard"], "paste cliphist"),
    ("screenshot", "Screenshot region", "\U000f0100", "Select an area; saved and copied", [RV, "screenshot", "region"], "capture grim"),
    ("screenshot-full", "Screenshot screen", "\U000f0100", "Whole screen; saved and copied", [RV, "screenshot", "full"], "capture grim"),
    ("picker", "Colour picker", "\U000f020a", "Copy a colour from the screen", ["hyprpicker", "-a"], "color eyedropper"),
    ("power-saver", "Power mode: saver", "\U000f0904", "Longer battery life", [RV, "power-mode", "saver"], "battery eco"),
    ("power-balanced", "Power mode: balanced", "\U000f0904", "Default", [RV, "power-mode", "balanced"], "battery"),
    ("power-performance", "Power mode: performance", "\U000f0241", "Fastest; more heat and fan", [RV, "power-mode", "performance"], "turbo boost"),
    ("wallpaper-next", "Wallpaper: next", "\U000f02e9", "Next picture from ~/Pictures", [RV, "wallpaper", "next"], "background image"),
    ("wallpaper-random", "Wallpaper: random", "\U000f02e9", "A random picture", [RV, "wallpaper", "random"], "background image shuffle"),
    ("wallpaper-none", "Wallpaper: none", "\U000f02e9", "Plain colour, least memory", [RV, "wallpaper", "none"], "background"),
    ("calendar-sync", "Sync calendars", "\U000f00ed", "Fetch Google/Outlook/ICS/Evolution events now", [RV, "calendar-sync"], "refresh"),
    ("dnd", "Do not disturb", "\U000f0a91", "Toggle notification popups", [RV, "notifications", "dnd"], "silence quiet"),
    ("bar", "Toggle bar", "\U000f10aa", "Show or hide the bar (Super+K)", [RV, "bar", "toggle"], "panel hide"),
    ("terminal", "Terminal", "\U000f018d", "Super+T", [RV, "app", "terminal"], "shell console foot"),
    ("lock", "Lock", "\U000f033e", "Super+L", [RV, "lock"], "screen"),
    ("suspend", "Suspend", "\U000f04b2", "Sleep now", [RV, "power", "suspend"], "sleep"),
    ("logout", "Log out", "\U000f0343", "End the Hyprland session", [RV, "power", "logout"], "exit quit"),
    ("reboot", "Restart", "\U000f0709", "Reboot the computer", [RV, "power", "reboot"], "reboot"),
    ("poweroff", "Shut down", "\U000f0425", "Power off the computer", [RV, "power", "poweroff"], "shutdown halt"),
    ("restart-shell", "Restart the bar", "\U000f0709", "Reload rv's Quickshell", [RV, "restart"], "reload quickshell"),
]
CONFIRM = {"logout", "reboot", "poweroff"}


def tool_dirs() -> list[Path]:
    dirs = [rvlib.REPO / "tools"]
    for entry in rvlib.settings().get("tools", {}).get("paths", []):
        path = rvlib.expand(entry)
        if path not in dirs:
            dirs.append(path)
    return [d for d in dirs if d.is_dir()]


def header(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    try:
        with path.open(errors="replace") as handle:
            for _, line in zip(range(30), handle):
                line = line.strip()
                if not line.startswith(("#", "//", "--")):
                    if line:
                        break
                    continue
                key, sep, value = line.lstrip("#/- ").partition(":")
                if sep and key.strip().lower() in {"name", "icon", "description", "terminal", "keywords"}:
                    meta[key.strip().lower()] = value.strip()
    except OSError:
        pass
    return meta


def user_tools() -> list[dict]:
    found: list[dict] = []
    for base in tool_dirs():
        for path in sorted(base.iterdir()):
            if path.name.startswith((".", "_")):
                continue
            if path.is_file() and os.access(path, os.X_OK):
                meta = header(path)
                found.append({
                    "id": f"user:{path.stem}", "name": meta.get("name") or path.stem.replace("-", " ").title(),
                    "icon": meta.get("icon", "\U000f1064"), "description": meta.get("description", str(path)),
                    "keywords": meta.get("keywords", ""), "exec": [str(path)],
                    "terminal": meta.get("terminal", "no").lower(),
                })
            elif path.is_dir() and (path / "tool.json").is_file():
                spec = rvlib.read_json(path / "tool.json", {})
                if not isinstance(spec, dict):
                    continue
                if "label" in spec and (path / "gui.sh").is_file():
                    # raven-shell tool: one entry per action.
                    actions = spec.get("actions") or [{"id": spec.get("directAction", "run"), "label": spec["label"]}]
                    for action in actions:
                        found.append({
                            "id": f"raven:{path.name}:{action.get('id')}",
                            "name": f"{spec['label']}: {action.get('label', action.get('id'))}",
                            "icon": spec.get("icon", "\U000f1064"), "description": spec.get("description", ""),
                            "keywords": path.name, "raven": [str(path / "gui.sh"), "action", str(action.get("id"))],
                            "terminal": "no",
                        })
                    continue
                command = spec.get("exec") or "run.sh"
                parts = shlex.split(command) if isinstance(command, str) else list(command)
                if parts and (path / parts[0]).exists():
                    parts[0] = str(path / parts[0])
                terminal = spec.get("terminal", False)
                found.append({
                    "id": f"user:{path.name}", "name": spec.get("name", path.name),
                    "icon": spec.get("icon", "\U000f1064"), "description": spec.get("description", ""),
                    "keywords": spec.get("keywords", ""), "exec": parts, "cwd": str(path),
                    "terminal": terminal if isinstance(terminal, str) else ("yes" if terminal else "no"),
                })
    return found


def all_tools() -> list[dict]:
    tools = [{"id": i, "name": n, "icon": g, "description": d, "exec": c, "keywords": k, "builtin": True}
             for i, n, g, d, c, k in BUILTINS
             if i != "picker" or rvlib.have("hyprpicker")]
    return tools + user_tools()


def run(tool_id: str, confirmed: bool = False) -> int:
    tool = next((t for t in all_tools() if t["id"] == tool_id), None)
    if tool is None:
        print(f"rv: no tool '{tool_id}'", file=sys.stderr)
        return 1
    if tool_id in CONFIRM and not confirmed:
        # From the launcher a stray Enter must not power off: ask in the power menu.
        rvlib.rv("power", "menu")
        return 0
    if "raven" in tool:
        status, out = rvlib.run(tool["raven"], timeout=600)
        try:
            reply = json.loads(out.splitlines()[-1])
            rvlib.notify(tool["name"], str(reply.get("message", "")))
        except (ValueError, IndexError):
            rvlib.notify(tool["name"], out[-300:] or f"exit {status}")
        return status
    mode = tool.get("terminal", "no")
    command = tool["exec"]
    if mode in ("yes", "true", "hold"):
        args = [RV, "term", "--float", "--title", tool["name"]]
        if mode == "hold":
            args.append("--hold")
        command = args + ["--"] + command
    subprocess.Popen(command, cwd=tool.get("cwd"), stdin=subprocess.DEVNULL, start_new_session=True)
    return 0


class ToolsApp(rvlib.App):
    title = "Utilities"
    keys_hint = "Enter run  ·  e edit tool  ·  n new tool  ·  o open folder"

    def refresh(self) -> None:
        self.tools = all_tools()

    def rows(self) -> list[rvlib.Row]:
        rows = [rvlib.Row("Built in", header=True)]
        rows += [rvlib.Row(t["name"], t["description"], data=t, icon=t["icon"]) for t in self.tools if t.get("builtin")]
        mine = [t for t in self.tools if not t.get("builtin")]
        rows.append(rvlib.Row("Your tools", header=True))
        if mine:
            rows += [rvlib.Row(t["name"], t["description"], data=t, icon=t["icon"], colour=rvlib.ACCENT) for t in mine]
        else:
            rows.append(rvlib.Row("Press n to create one", "~/.config/rv/tools", data=None, colour=rvlib.DIM))
        return rows

    def detail(self, row: rvlib.Row | None) -> list[str]:
        if row is None or not row.data:
            return ["Tools are scripts in ~/.config/rv/tools — see tools/README.md"]
        t = row.data
        return [f"id: {t['id']}", "runs: " + " ".join(t.get("exec") or t.get("raven") or [])]

    def on_key(self, key: int, row: rvlib.Row | None) -> None:
        if key in rvlib.ENTER and row is not None:
            if row.data is None:
                self.new_tool()
                return
            if row.data["id"] in CONFIRM and not self.confirm(row.data["name"]):
                return
            run(row.data["id"], confirmed=True)
            if row.data.get("builtin") and row.data["id"] not in ("bar", "dnd"):
                self.running = False
        elif key == ord("n"):
            self.new_tool()
        elif key == ord("o"):
            folder = rvlib.CONFIG_HOME / "tools"
            folder.mkdir(parents=True, exist_ok=True)
            rvlib.rv("term", "--float", "--", "sh", "-c", f"cd {shlex.quote(str(folder))} && exec ${{SHELL:-bash}}")
        elif key == ord("e") and row is not None and row.data and not row.data.get("builtin"):
            target = (row.data.get("exec") or row.data.get("raven"))[0]
            self.edit(Path(target))

    def edit(self, path: Path) -> None:
        import curses
        curses.endwin()
        editor = rvlib.settings()["apps"].get("editor", "vim")
        subprocess.call(shlex.split(editor if editor != "auto" else "vim") + [str(path)])
        self.screen.refresh()
        self.refresh()

    def new_tool(self) -> None:
        name = self.prompt("New tool name")
        if not name:
            return
        slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-") or "tool"
        folder = rvlib.CONFIG_HOME / "tools"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{slug}.sh"
        if not path.exists():
            path.write_text(TEMPLATE.format(name=name))
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.edit(path)
        self.flash(f"Created {path}", rvlib.GOOD)


TEMPLATE = """#!/usr/bin/env bash
# name: {name}
# icon: 󱁤
# description: What this does, shown in the launcher
# terminal: hold
# keywords: words to search by
#
# terminal: no   → runs in the background (use notify-send to report back)
# terminal: yes  → opens in a floating terminal, closes when done
# terminal: hold → opens in a floating terminal and waits for a key at the end
set -euo pipefail

echo "Hello from {name}"
"""


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "list":
        tools = all_tools()
        if "--json" in argv:
            print(json.dumps([{k: t[k] for k in ("id", "name", "icon", "description", "keywords") if k in t}
                              for t in tools], ensure_ascii=False))
        else:
            for t in tools:
                print(f"{t['id']:<24} {t['name']:<22} {t['description']}")
        return 0
    if len(argv) >= 3 and argv[1] == "run":
        return run(argv[2], confirmed="--yes" in argv)
    rvlib.guard(ToolsApp().start)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
