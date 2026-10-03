#!/usr/bin/env python3
"""rv display: monitors in a terminal.

Arrange (first tab) — a live picture of the layout:
  n / p or 1–9     select a monitor
  ←↓↑→ or h j k l  move it 100 px (H J K L: 10 px); edges snap together
  + / -            scale up / down — the box resizes as you go
  o rotate · m resolution · e on/off · s snap to the nearest screen · u undo
  a                apply: keep it (or it reverts in 15 s), then choose
                   whether to remember it for every login
Details (Tab) — the same settings as a list, mirroring and quick layouts.
Nothing changes on screen until you apply.
"""

from __future__ import annotations

import curses
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rvlib  # noqa: E402
from rvlib import Row  # noqa: E402

MONITORS_FILE = rvlib.CONFIG_HOME / "monitors.lua"
SCALES = ["1", "1.25", "1.333333", "1.5", "1.6", "1.666667", "1.75", "2", "2.5", "3"]
POSITIONS = ["auto", "auto-right", "auto-left", "auto-up", "auto-down", "custom…"]
ROTATIONS = ["normal", "90°", "180°", "270°", "flipped", "flipped 90°", "flipped 180°", "flipped 270°"]


@dataclass
class Rule:
    name: str
    description: str = ""
    enabled: bool = True
    mode: str = "preferred"
    position: str = "auto"
    scale: str = "1"
    transform: int = 0
    mirror: str = ""
    modes: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    x: int = 0
    y: int = 0

    def lua(self) -> str:
        if not self.enabled:
            return f'{{ output = {json.dumps(self.name)}, disabled = true }}'
        parts = [f"output = {json.dumps(self.name)}", f"mode = {json.dumps(self.mode)}",
                 f"position = {json.dumps(self.position)}",
                 f"scale = {self.scale if self.scale != 'auto' else json.dumps('auto')}",
                 f"transform = {self.transform}"]
        if self.mirror:
            parts.append(f"mirror = {json.dumps(self.mirror)}")
        return "{ " + ", ".join(parts) + " }"

    def key(self) -> tuple:
        return (self.enabled, self.mode, self.position, self.scale, self.transform, self.mirror)


def fmt_scale(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text


FAKE = os.environ.get("RV_FAKE_MONITORS")  # tests: read monitors from a JSON file, apply nothing


def live() -> list[Rule]:
    raw = Path(FAKE).read_text() if FAKE else rvlib.output(["hyprctl", "monitors", "all", "-j"])
    try:
        monitors = json.loads(raw)
    except ValueError:
        return []
    rules = []
    for m in monitors:
        modes = [re.sub(r"Hz$", "", mode) for mode in m.get("availableModes", [])]
        mode = f"{m['width']}x{m['height']}@{m['refreshRate']:.2f}"
        mirror = m.get("mirrorOf", "none")
        rules.append(Rule(
            name=m["name"], description=f"{m.get('make', '')} {m.get('model', '')}".strip() or m.get("description", ""),
            enabled=not m.get("disabled", False), mode=mode, position=f"{m['x']}x{m['y']}",
            scale=fmt_scale(m.get("scale", 1)), transform=int(m.get("transform", 0)),
            mirror="" if mirror in ("none", "", None) else mirror, modes=modes,
            width=m["width"], height=m["height"], x=m["x"], y=m["y"]))
    return rules


def pixels(rule: Rule) -> tuple[int, int]:
    match = re.match(r"(\d+)x(\d+)", rule.mode)
    return (int(match.group(1)), int(match.group(2))) if match else (rule.width, rule.height)


def logical(rule: Rule) -> tuple[float, float]:
    """Size in layout pixels: resolution ÷ scale, swapped when rotated 90°/270°."""
    w, h = pixels(rule)
    scale = float(rule.scale) if rule.scale not in ("auto", "") else 1.0
    w, h = w / scale, h / scale
    return (h, w) if rule.transform % 2 else (w, h)


def apply_rule(rule: Rule) -> tuple[bool, str]:
    if FAKE:
        return True, "ok"
    status, out = rvlib.run(["hyprctl", "eval", f"hl.monitor({rule.lua()})"])
    return status == 0 and out.strip() == "ok", out


def save(rules: list[Rule]) -> None:
    lines = ["-- Written by `rv display`. Edit freely, or re-save from the app.",
             "-- Outputs not listed here use the automatic rule in hyprland.lua.", "return {"]
    lines += [f"    {rule.lua()}," for rule in rules]
    lines.append("}")
    MONITORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    MONITORS_FILE.write_text("\n".join(lines) + "\n")


class DisplayApp(rvlib.App):
    title = "Displays"
    tabs = ["Arrange", "Details"]
    keys_hint = "h/l change · Enter pick · a apply · w save for login"
    SNAP = 48  # layout pixels: closer than this, edges stick together

    def __init__(self) -> None:
        super().__init__()
        self.rules: list[Rule] = []
        self.original: dict[str, Rule] = {}
        self.sel = 0

    def refresh(self) -> None:
        self.rules = live()
        self.original = {r.name: replace(r) for r in self.rules}
        self.sel = min(self.sel, max(0, len(self.rules) - 1))

    # ---- Arrange: geometry ----------------------------------------------------
    def placed(self) -> list[Rule]:
        """Monitors that occupy their own area (on, not mirroring)."""
        return [r for r in self.rules if r.enabled and not r.mirror]

    @staticmethod
    def box(rule: Rule) -> tuple[float, float, float, float]:
        w, h = logical(rule)
        return rule.x, rule.y, w, h

    @staticmethod
    def overlaps(a, b) -> bool:
        return a[0] < b[0] + b[2] - 1 and b[0] < a[0] + a[2] - 1 and a[1] < b[1] + b[3] - 1 and b[1] < a[1] + a[3] - 1

    def problems(self) -> list[str]:
        placed = self.placed()
        out = []
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                if self.overlaps(self.box(a), self.box(b)):
                    out.append(f"{a.name} and {b.name} overlap")
        if len(placed) > 1:
            for r in placed:
                if not any(self.touching(self.box(r), self.box(o)) for o in placed if o is not r):
                    out.append(f"{r.name} does not touch another screen — the pointer cannot cross over")
        return out

    @staticmethod
    def touching(a, b) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        vertical = ay < by + bh and by < ay + ah
        horizontal = ax < bx + bw and bx < ax + aw
        return (vertical and (abs(ax + aw - bx) < 1 or abs(bx + bw - ax) < 1)) or \
               (horizontal and (abs(ay + ah - by) < 1 or abs(by + bh - ay) < 1))

    def snap_candidates(self, rule: Rule) -> list[tuple[float, int, int]]:
        """Positions where `rule` touches a neighbour without overlapping any screen."""
        ax, ay, aw, ah = self.box(rule)
        others = [o for o in self.placed() if o is not rule]
        found = []
        for o in others:
            bx, by, bw, bh = self.box(o)
            clamp_y = min(max(ay, by - ah + 1), by + bh - 1)
            clamp_x = min(max(ax, bx - aw + 1), bx + bw - 1)
            for x, y in ((bx + bw, clamp_y), (bx - aw, clamp_y), (clamp_x, by + bh), (clamp_x, by - ah)):
                # Align with the neighbour's edge when nearly aligned.
                if abs(y - by) < self.SNAP:
                    y = by
                if abs(x - bx) < self.SNAP:
                    x = bx
                spot = (x, y, aw, ah)
                if any(self.overlaps(spot, self.box(p)) for p in others):
                    continue
                found.append((abs(x - ax) + abs(y - ay), int(round(x)), int(round(y))))
        return sorted(found)

    def place(self, rule: Rule, x: float, y: float) -> None:
        rule.x, rule.y = int(round(x)), int(round(y))
        rule.position = f"{rule.x}x{rule.y}"

    def nudge(self, dx: int, dy: int) -> None:
        rule = self.selected_rule()
        if rule is None or not rule.enabled or rule.mirror:
            return
        self.place(rule, rule.x + dx, rule.y + dy)
        near = self.snap_candidates(rule)
        if near and near[0][0] <= self.SNAP:
            self.place(rule, near[0][1], near[0][2])

    def snap(self) -> None:
        rule = self.selected_rule()
        near = self.snap_candidates(rule) if rule else []
        if near:
            self.place(rule, near[0][1], near[0][2])
            self.flash(f"{rule.name} snapped to its nearest neighbour", rvlib.GOOD, 2)
        elif rule and len(self.placed()) > 1:
            self.flash("No free spot next to another screen", rvlib.WARN)

    def rescale(self, step: int) -> None:
        rule = self.selected_rule()
        if rule is None:
            return
        before = self.box(rule)
        attached = any(self.touching(before, self.box(o)) or self.overlaps(before, self.box(o))
                       for o in self.placed() if o is not rule)
        index = SCALES.index(rule.scale) if rule.scale in SCALES else SCALES.index("1")
        rule.scale = SCALES[max(0, min(len(SCALES) - 1, index + step))]
        after = self.box(rule)
        # Stay attached to the neighbour: a shrinking screen would otherwise
        # leave a gap, a growing one would overlap.
        reach = self.SNAP + abs(after[2] - before[2]) + abs(after[3] - before[3])
        near = self.snap_candidates(rule)
        if near and (attached or near[0][0] <= reach):
            self.place(rule, near[0][1], near[0][2])

    def selected_rule(self) -> Rule | None:
        return self.rules[self.sel] if 0 <= self.sel < len(self.rules) else None

    # ---- Arrange: drawing -------------------------------------------------------
    def draw(self) -> None:
        if self.tab != 0:
            super().draw()
            return
        s = self.screen
        s.erase()
        h, w = s.getmaxyx()
        A = rvlib.attr
        self.put(0, 2, self.title, w - 4, A(rvlib.TITLE, curses.A_BOLD))
        x = len(self.title) + 5
        for i, name in enumerate(self.tabs):
            label = f" {name} "
            self.put(0, x, label, w - x, A(rvlib.SELECTED, curses.A_BOLD) if i == self.tab else A(rvlib.DIM))
            x += len(label) + 1
        self.put(1, 2, "─" * (w - 4), w - 4, A(rvlib.DIM))

        info_lines = 6
        top, left = 3, 3
        ch, cw = max(6, h - top - info_lines - 4), w - 6
        placed = self.placed()
        if placed:
            boxes = [self.box(r) for r in placed]
            x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
            x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
            pad_x, pad_y = (x1 - x0) * 0.08 + 1, (y1 - y0) * 0.08 + 1
            x0, x1, y0, y1 = x0 - pad_x, x1 + pad_x, y0 - pad_y, y1 + pad_y
            # Terminal cells are about twice as tall as wide.
            k = min((cw - 1) / (x1 - x0), (ch - 1) * 2 / (y1 - y0))
            off_x = left + int((cw - (x1 - x0) * k) / 2)
            off_y = top + int((ch - (y1 - y0) * k / 2) / 2)
            problems = self.problems()
            order = [r for r in placed if r is not self.selected_rule()] + [r for r in placed if r is self.selected_rule()]
            for rule in order:
                bx, by, bw, bh = self.box(rule)
                c0 = off_x + int((bx - x0) * k); c1 = off_x + int((bx + bw - x0) * k) - 1
                r0 = off_y + int((by - y0) * k / 2); r1 = off_y + int((by + bh - y0) * k / 2) - 1
                c1, r1 = max(c1, c0 + 6), max(r1, r0 + 2)
                chosen = rule is self.selected_rule()
                bad = any(rule.name in p and "overlap" in p for p in problems)
                colour = A(rvlib.BAD, curses.A_BOLD) if bad else A(rvlib.ACCENT, curses.A_BOLD) if chosen else A(rvlib.DIM)
                tl, tr, bl, br, hz, vt = ("╔", "╗", "╚", "╝", "═", "║") if chosen else ("┌", "┐", "└", "┘", "─", "│")
                inner = c1 - c0 - 1
                self.put(r0, c0, tl + hz * inner + tr, inner + 2, colour)
                for r in range(r0 + 1, r1):
                    self.put(r, c0, vt, 1, colour)
                    self.put(r, c1, vt, 1, colour)
                self.put(r1, c0, bl + hz * inner + br, inner + 2, colour)
                lw, lh = logical(rule)
                px = pixels(rule)
                labels = [rule.name, f"{px[0]}×{px[1]} · {rule.scale}×", f"{int(lw)}×{int(lh)} at {rule.x},{rule.y}"]
                mid = (r0 + r1) // 2 - 1
                for n, text in enumerate(labels):
                    if r0 < mid + n < r1 and inner > 2:
                        text = text[:inner - 1]
                        self.put(mid + n, c0 + 1 + max(0, (inner - len(text)) // 2), text, inner,
                                 colour if n == 0 else A(rvlib.DIM))
        else:
            self.put(top + 2, left, "No screen is on", cw, A(rvlib.BAD))

        # Selected monitor and status.
        y = h - info_lines - 3
        self.put(y, 2, "─" * (w - 4), w - 4, A(rvlib.DIM))
        rule = self.selected_rule()
        names = "  ".join(f"[{i + 1}] {r.name}" + ("" if r.enabled else " (off)") + (" (mirror)" if r.mirror else "")
                          for i, r in enumerate(self.rules))
        self.put(y + 1, 3, names, w - 6, A(rvlib.TITLE, curses.A_BOLD))
        if rule:
            lw, lh = logical(rule)
            state = "off" if not rule.enabled else (f"mirrors {rule.mirror}" if rule.mirror else "on")
            self.put(y + 2, 3, f"{rule.name}  {rule.description}  ·  {state}", w - 6)
            self.put(y + 3, 3, f"resolution {rule.mode}   scale {rule.scale}   looks like {int(lw)}×{int(lh)}   "
                     f"rotation {ROTATIONS[rule.transform]}   position {rule.x},{rule.y}", w - 6, A(rvlib.DIM))
        issues = self.problems()
        pending = len(self.changed())
        if issues:
            self.put(y + 4, 3, "! " + issues[0], w - 6, A(rvlib.WARN))
        elif pending:
            self.put(y + 4, 3, f"{pending} screen(s) changed — press a to apply", w - 6, A(rvlib.ACCENT))
        else:
            self.put(y + 4, 3, "Matches what is on screen now", w - 6, A(rvlib.DIM))

        self.put(h - 2, 2, "─" * (w - 4), w - 4, A(rvlib.DIM))
        import time as _time
        if self.message and _time.monotonic() < self.message_until:
            self.put(h - 1, 2, self.message, w - 4, A(self.message_colour, curses.A_BOLD))
        else:
            self.put(h - 1, 2, "n/p select · arrows move (HJKL fine) · +/- scale · o rotate · m resolution · e on/off · "
                     "s snap · u undo · a apply · Tab details · q quit", w - 4, A(rvlib.DIM))
        s.refresh()

    def intercept(self, key: int) -> int | None:
        if self.tab != 0 or key in (9, curses.KEY_BTAB, ord("q"), 27):
            return key
        rule = self.selected_rule()
        moves = {curses.KEY_LEFT: (-100, 0), ord("h"): (-100, 0), curses.KEY_RIGHT: (100, 0), ord("l"): (100, 0),
                 curses.KEY_UP: (0, -100), ord("k"): (0, -100), curses.KEY_DOWN: (0, 100), ord("j"): (0, 100),
                 ord("H"): (-10, 0), ord("L"): (10, 0), ord("K"): (0, -10), ord("J"): (0, 10),
                 curses.KEY_SLEFT: (-10, 0), curses.KEY_SRIGHT: (10, 0), 337: (0, -10), 336: (0, 10)}
        if key in moves:
            self.nudge(*moves[key])
        elif key in (ord("n"), ord(" "), ord("]")):
            self.sel = (self.sel + 1) % max(1, len(self.rules))
        elif key in (ord("p"), ord("[")):
            self.sel = (self.sel - 1) % max(1, len(self.rules))
        elif ord("1") <= key <= ord("9") and key - ord("1") < len(self.rules):
            self.sel = key - ord("1")
        elif key in (ord("+"), ord("=")):
            self.rescale(1)
        elif key in (ord("-"), ord("_")):
            self.rescale(-1)
        elif key == ord("o") and rule:
            rule.transform = (rule.transform + 1) % 4 if rule.transform < 4 else 0
        elif key == ord("m") and rule:
            self.pick("mode", rule)
        elif key == ord("e") and rule:
            self.cycle("enabled", rule, 1)
            if rule.enabled and len(self.placed()) > 1:
                near = self.snap_candidates(rule)
                if near:
                    self.place(rule, near[0][1], near[0][2])
        elif key == ord("s"):
            self.snap()
        elif key == ord("u"):
            self.refresh()
            self.flash("Back to what is on screen")
        elif key == ord("a"):
            self.apply()
        elif key == ord("w"):
            self.on_key(key, None)
        elif key == ord("r"):
            return key
        return None

    def changed(self) -> list[Rule]:
        return [r for r in self.rules if r.key() != self.original[r.name].key()]

    def rows(self) -> list[Row]:
        rows = [Row("Quick layouts", header=True)]
        if len(self.rules) > 1:
            first = self.rules[0].name
            rows += [
                Row("Extend: others to the right", data=("preset", "extend"), icon="\U000f0379"),
                Row(f"Mirror {first} on all screens", data=("preset", "mirror"), icon="\U000f0379"),
                Row(f"Only {first}", data=("preset", "first"), icon="\U000f0379"),
                Row("Only the external screen(s)", data=("preset", "external"), icon="\U000f0379"),
            ]
        else:
            rows.append(Row("Connect another screen for extend / mirror layouts", colour=rvlib.DIM))
        for rule in self.rules:
            edited = rule.key() != self.original[rule.name].key()
            rows.append(Row(f"{rule.name}  {rule.description}" + ("  (edited)" if edited else ""), header=True))
            rows.append(Row("Enabled", "● on" if rule.enabled else "○ off", data=("enabled", rule)))
            if rule.enabled:
                rows.append(Row("Resolution", rule.mode, data=("mode", rule)))
                rows.append(Row("Scale", rule.scale, data=("scale", rule)))
                rows.append(Row("Position", rule.position, data=("position", rule)))
                rows.append(Row("Rotation", ROTATIONS[rule.transform], data=("transform", rule)))
                if len(self.rules) > 1:
                    rows.append(Row("Mirror of", rule.mirror or "—", data=("mirror", rule)))
        return rows

    def detail(self, row: Row | None) -> list[str]:
        return self.diagram() + ([f"{len(self.changed())} unapplied change(s) — a applies"] if self.changed() else [])

    def diagram(self, cols: int = 56, lines: int = 7) -> list[str]:
        boxes = []
        for r in self.rules:
            if not r.enabled or r.mirror:
                continue
            scale = float(r.scale) if r.scale not in ("auto", "") else 1
            w, h = r.width / scale, r.height / scale
            if r.transform % 2:
                w, h = h, w
            boxes.append((r.name, r.x, r.y, w, h))
        if not boxes:
            return []
        x0 = min(b[1] for b in boxes); y0 = min(b[2] for b in boxes)
        x1 = max(b[1] + b[3] for b in boxes); y1 = max(b[2] + b[4] for b in boxes)
        k = min((cols - 1) / max(1, x1 - x0), (lines - 1) * 2 / max(1, y1 - y0))
        grid = [[" "] * cols for _ in range(lines)]
        for name, x, y, w, h in boxes:
            c0, c1 = int((x - x0) * k), max(int((x - x0) * k) + 4, int((x - x0 + w) * k))
            r0, r1 = int((y - y0) * k / 2), max(int((y - y0) * k / 2) + 2, int((y - y0 + h) * k / 2))
            c1, r1 = min(c1, cols - 1), min(r1, lines - 1)
            for c in range(c0, c1 + 1):
                grid[r0][c] = grid[r1][c] = "─"
            for r in range(r0, r1 + 1):
                grid[r][c0] = grid[r][c1] = "│"
            grid[r0][c0], grid[r0][c1], grid[r1][c0], grid[r1][c1] = "┌", "┐", "└", "┘"
            label = name[: max(0, c1 - c0 - 1)]
            mid = (r0 + r1) // 2
            for i, ch in enumerate(label):
                grid[mid][c0 + 1 + i] = ch
        return ["".join(line).rstrip() for line in grid]

    # Editing ------------------------------------------------------------------
    def cycle(self, what: str, rule: Rule, step: int) -> None:
        if what == "enabled":
            if rule.enabled and sum(r.enabled for r in self.rules) == 1:
                self.flash("At least one screen must stay on", rvlib.WARN)
                return
            rule.enabled = not rule.enabled
        elif what == "mode":
            options = rule.modes or [rule.mode]
            current = next((i for i, m in enumerate(options) if m.split("@")[0] == rule.mode.split("@")[0]
                            and abs(float(m.split("@")[1]) - float(rule.mode.split("@")[1])) < 0.5), 0) \
                if "@" in rule.mode else 0
            rule.mode = options[(current + step) % len(options)]
        elif what == "scale":
            index = SCALES.index(rule.scale) if rule.scale in SCALES else 0
            rule.scale = SCALES[(index + step) % len(SCALES)]
        elif what == "position":
            choices = POSITIONS[:-1]
            index = choices.index(rule.position) if rule.position in choices else -1
            rule.position = choices[(index + step) % len(choices)]
        elif what == "transform":
            rule.transform = (rule.transform + step) % 8
        elif what == "mirror":
            options = [""] + [r.name for r in self.rules if r.name != rule.name]
            index = options.index(rule.mirror) if rule.mirror in options else 0
            rule.mirror = options[(index + step) % len(options)]

    def pick(self, what: str, rule: Rule) -> None:
        if what == "mode":
            picked = self.choose(f"{rule.name} resolution", rule.modes or [rule.mode])
            if picked:
                rule.mode = picked
        elif what == "scale":
            picked = self.choose(f"{rule.name} scale", SCALES + ["custom…"], rule.scale)
            if picked == "custom…":
                text = self.prompt("Scale (0.5–4)")
                try:
                    if text and 0.5 <= float(text) <= 4:
                        rule.scale = fmt_scale(float(text))
                except ValueError:
                    self.flash("Not a number", rvlib.BAD)
            elif picked:
                rule.scale = picked
        elif what == "position":
            picked = self.choose(f"{rule.name} position", POSITIONS, rule.position)
            if picked == "custom…":
                text = self.prompt("Position as X,Y in logical pixels", rule.position.replace("x", ","))
                match = re.fullmatch(r"\s*(-?\d+)\s*[,x ]\s*(-?\d+)\s*", text or "")
                if match:
                    rule.position = f"{match.group(1)}x{match.group(2)}"
                elif text:
                    self.flash("Use X,Y — e.g. 1440,0", rvlib.BAD)
            elif picked:
                rule.position = picked
        elif what == "transform":
            picked = self.choose(f"{rule.name} rotation", ROTATIONS, ROTATIONS[rule.transform])
            if picked:
                rule.transform = ROTATIONS.index(picked)
        elif what == "mirror":
            options = ["(none)"] + [r.name for r in self.rules if r.name != rule.name]
            picked = self.choose(f"{rule.name} mirrors", options, rule.mirror or "(none)")
            if picked:
                rule.mirror = "" if picked == "(none)" else picked
        else:
            self.cycle(what, rule, 1)

    def preset(self, kind: str) -> None:
        first, others = self.rules[0], self.rules[1:]
        for rule in self.rules:
            rule.mirror = ""
            rule.enabled = True
        if kind == "extend":
            first.position = "0x0"
            for rule in others:
                rule.position = "auto-right"
        elif kind == "mirror":
            for rule in others:
                rule.mirror = first.name
        elif kind == "first":
            for rule in others:
                rule.enabled = False
        elif kind == "external":
            first.enabled = False
            for rule in others:
                rule.position = "auto"
        self.apply()

    # Applying ----------------------------------------------------------------
    def apply(self) -> None:
        # Arranged screens get exact positions, shifted so the layout starts at 0,0.
        placed = self.placed()
        if placed and any("x" in r.position and not r.position.startswith("auto") for r in placed):
            min_x = min(r.x for r in placed)
            min_y = min(r.y for r in placed)
            for r in placed:
                if not r.position.startswith("auto") or r.position != self.original[r.name].position:
                    self.place(r, r.x - min_x, r.y - min_y)
        overlaps = [p for p in self.problems() if "overlap" in p]
        if overlaps and not self.confirm(overlaps[0] + " — apply anyway"):
            return
        changed = self.changed()
        if not changed:
            self.flash("Nothing to apply")
            return
        previous = [self.original[r.name] for r in changed]
        # Enable/move screens before disabling others, so one always stays on.
        for rule in sorted(changed, key=lambda r: not r.enabled):
            ok, out = apply_rule(rule)
            if not ok:
                self.flash(f"{rule.name}: {out}", rvlib.BAD, 8)
                self.restore(previous)
                return
            time.sleep(0.15)
        if not self.keep():
            self.restore(previous)
            self.flash("Reverted", rvlib.WARN)
            return
        applied = [replace(r) for r in self.rules]
        self.refresh()
        if self.confirm("Kept. Remember this layout for future logins"):
            save(applied)
            self.flash(f"Remembered in {MONITORS_FILE}", rvlib.GOOD, 6)
        else:
            self.flash("Kept for this session only (w remembers it later)", rvlib.GOOD, 6)

    def restore(self, rules: list[Rule]) -> None:
        for rule in sorted(rules, key=lambda r: not r.enabled):
            apply_rule(replace(rule, position=f"{rule.x}x{rule.y}"))
            time.sleep(0.15)
        self.refresh()

    def keep(self, seconds: int = 15) -> bool:
        s = self.screen
        s.timeout(1000)
        try:
            for left in range(seconds, 0, -1):
                h, w = s.getmaxyx()
                s.move(h - 1, 0)
                s.clrtoeol()
                self.put(h - 1, 2, f"Keep this layout? y keep · n revert — reverting in {left} s", w - 4,
                         rvlib.attr(rvlib.WARN, curses.A_BOLD))
                s.refresh()
                key = s.getch()
                if key in (ord("y"), ord("Y"), 10, 13):
                    return True
                if key in (ord("n"), ord("N"), 27):
                    return False
            return False
        finally:
            s.timeout(self._timeout())

    def on_key(self, key: int, row: Row | None) -> None:
        if key == ord("a"):
            self.apply()
            return
        if key == ord("w"):
            if self.changed() and not self.confirm("Save includes unapplied edits — continue"):
                return
            save(self.rules)
            self.flash(f"Saved to {MONITORS_FILE}", rvlib.GOOD)
            return
        if row is None or not row.data:
            return
        what, target = row.data
        if what == "preset":
            if key in rvlib.ENTER:
                self.preset(target)
        elif key in rvlib.ENTER:
            self.pick(what, target)
        elif key in rvlib.LEFT:
            self.cycle(what, target, -1)
        elif key in rvlib.RIGHT:
            self.cycle(what, target, 1)


if __name__ == "__main__":
    rvlib.guard(DisplayApp().start)
