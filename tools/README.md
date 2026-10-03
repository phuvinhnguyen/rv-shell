# Your own utilities

Anything you drop in `~/.config/rv/tools/` shows up in the launcher
(`Super+A` while searching, or `Super+Shift+A` for utilities only) and in
`rv open tools`. No restart needed — the list is read each time it opens.

The quickest way: `rv open tools`, press **n**, give it a name. You get a
script from a template, opened in your editor.

## 1. A script

Any executable file. Comments at the top describe it (all optional):

```bash
#!/usr/bin/env bash
# name: Disk usage
# icon: 󰋊
# description: What fills my home folder
# terminal: hold
# keywords: space storage du
ncdu ~ 2>/dev/null || du -h --max-depth=1 ~ | sort -h
```

| `terminal:` | runs                                                       |
| ----------- | ---------------------------------------------------------- |
| `no`        | in the background — report back with `notify-send`         |
| `yes`       | in a floating terminal that closes when the script ends    |
| `hold`      | in a floating terminal that stays open until you press a key |

Icons are any text; Nerd Font glyphs fit best (<https://www.nerdfonts.com/cheat-sheet>).

## 2. A folder with `tool.json`

For tools with several files:

```
~/.config/rv/tools/translate/
├── tool.json
└── run.py
```

```json
{
  "name": "Translate clipboard",
  "icon": "󰗊",
  "description": "English ⇄ Vietnamese",
  "exec": "python3 run.py",
  "terminal": "hold",
  "keywords": "language"
}
```

`exec` runs inside the folder; a first word naming a file in the folder is
resolved to it.

## 3. raven-shell tools

Folders from `../raven-shell/tools` (a `tool.json` with `label` plus a
`gui.sh`) work unchanged: every action becomes its own entry, and the JSON
reply's `message` is shown as a notification. Add the folder in
`rv settings` → or directly in `~/.config/rv/settings.json`:

```json
{ "tools": { "paths": ["~/.config/rv/tools", "~/.Settings/raven-shell/tools"] } }
```

## Handy building blocks

| need                         | use                                         |
| ---------------------------- | ------------------------------------------- |
| clipboard in / out           | `wl-paste`, `wl-copy`                       |
| pick a screen region         | `slurp` (with `grim -g` to capture it)      |
| a notification               | `notify-send -a rv "Title" "Body"`          |
| a pick list in the terminal  | `fzf`                                       |
| open another rv app          | `rv open wifi` (see `rv help`)              |
| a Python TUI that looks like rv | `import rvlib` from the repository's `tui/` and subclass `rvlib.App` |

The scripts in this folder (`qr-clipboard.sh`, `ocr-region.sh`, `weather.sh`)
are working examples.
