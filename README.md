# rv — a lean Hyprland desktop for Debian

Hyprland + one Quickshell process + small terminal apps. A left bar that
shows what matters; everything else (settings, Wi-Fi, Bluetooth, displays,
audio, calendar) opens as a floating terminal app when you need it and is gone
when you close it.

```
┌────┐
│   │  launcher: apps · utilities · clipboard · run · calc · web
│ 1  │  workspaces (scroll to switch)
│ •  │
│    │
│ 21 │  clock — hover: month + events, click: calendar
│ 47 │
│    │
│ ♪  │  media (only while something plays)
│ ◔  │  CPU / memory
│ ⋮  │  tray
│ 󰤨  │  Wi-Fi · Bluetooth · volume · battery
│ 󰂚  │  notifications
│ 󰒓  │  settings
│ ⏻  │  power: lock, suspend, power mode, log out…
└────┘
```

## Memory

Measured on Debian 13, Hyprland 0.55, Quickshell 0.3:

| what                         | resident memory                       |
| ---------------------------- | ------------------------------------- |
| the whole shell, idle        | ~137 MB (≈40 MB of it shared libraries) |
| a bare Quickshell window     | ~98 MB — the floor for any Quickshell bar |
| a terminal app while open    | ~15 MB (Python), 0 once closed        |

How it stays small:

- **One process** for bar, launcher, notifications, OSD, lock and idle.
- **Nothing hidden is alive**: the launcher, popups, toasts, OSD, lock screen
  and wallpaper are created when shown and destroyed when hidden.
- **Software rendering** (`settings → Apps → Shell renderer`): skips loading
  the GPU driver into the shell; saves ~65 MB here.
- **No polling** for Wi-Fi, Bluetooth, audio, battery, workspaces — all of it
  arrives as DBus/PipeWire/Hyprland events. CPU and memory read `/proc` every
  3 s, only while shown.
- **No QtWidgets**: tray menus are drawn in QML.
- **Settings are terminal apps**, not a resident GUI.
- **One foot server** shares fonts and glyph cache between all terminals.
- Blur, shadows and the wallpaper are off by default.

## Install

```bash
git clone <this repo> ~/.Settings/hypr-dotfiles && cd ~/.Settings/hypr-dotfiles
./install.sh              # shows the plan and current state; changes nothing
./install.sh --all        # apt packages (sudo) + Nerd Font if missing + links
```

Or step by step: `--packages` (`--extras` for the optional ones), `--fonts`,
`--blesh`, `--apply`. `--rollback` undoes `--apply` from the backup it made in
`~/.local/state/rv/backups/`.

On Debian 13, `hyprland`, `quickshell` and `hyprpicker` come from
**trixie-backports** (the installer tells you the one-line fix if apt can't
find them). The wallpapers in `wallpapers/` are stored with Git LFS: install
`git-lfs` and run `git lfs pull` if you want them.

`--apply` links:

| target                    | from                    |
| ------------------------- | ----------------------- |
| `~/.config/hypr`          | `config/hypr`           |
| `~/.config/foot/foot.ini` | `config/foot/foot.ini`  |
| `~/.vimrc`                | `config/vim/vimrc`      |
| `~/.local/bin/rv`         | `bin/rv`                |
| `~/.bashrc` (one line)    | `config/bash/rv.bash`   |

Then log in to Hyprland, or in a running session: `hyprctl reload && rv restart`.

## Keys

Same layout as raven-shell. `Super+/` lists every binding live.

| keys | action |
| --- | --- |
| `Super+A` | launcher (apps + utilities) — `;` utilities · `:` clipboard · `>` run · `=` calc · `?` web search (Enter searches; Enter on a result opens it; Shift+Enter opens DuckDuckGo) |
| `Super+Shift+A` | utilities |
| `Super+V` | clipboard history (Shift+Del removes an entry) |
| `Super+N` | settings |
| `Super+Shift+N` · `Ctrl+Alt+C` | notification list · clear notifications |
| `Super+K` | hide / show the bar |
| `Super+L` · `Super+Shift+L` | lock · suspend |
| `Super+Esc` | power menu |
| `Super+Shift+P` | power mode: saver → balanced → performance |
| `Super+P` | displays |
| `Super+/` | keybinding cheatsheet |
| `Super+Shift+E` | emoji |
| `Ctrl+Shift+Esc` | system monitor |
| `Super+T` / `Super+Enter` · `B` · `C` · `E` | terminal · browser · editor · files |
| `Super+Shift+S` · `Print` | screenshot region · screen (saved + copied) |
| `Super+1…0` · `Super+Shift+1…0` | workspace · move window there |
| `Ctrl+Super+1…0` | workspace groups (same slot in group N) |
| `Super+,` / `Super+.` / `Super+scroll` | previous / next workspace |
| `Super+S` · `Super+Shift+X` | scratchpad · send window to it |
| `Super+Q` · `F` · `W` · `G` | close · fullscreen · float · group |
| `Super+Tab` | overview (scrolling layout) |
| `Super+arrows` · `+Shift` | focus · move window |
| `Ctrl+Super+arrows` · `+Shift` | move pointer · resize window |
| `Ctrl+Super+Enter` · `+Shift` | left · right click |

Bar: scroll the volume icon to change volume, right-click it to mute;
right-click Bluetooth to switch it on/off; click the battery for the power
mode; right-click the bell for do-not-disturb; right-click the launcher button
for utilities.

## Terminal apps

`rv open NAME` (running it again closes the app). Common keys: `j/k` move,
`h/l` change, `Enter` act, `Tab` next section, `r` refresh, `q` quit.

| app | what |
| --- | --- |
| `settings` | bar, theme (presets, wallpaper), windows, input, idle, apps — applied live |
| `wifi` | scan, connect, hidden networks, forget, `e` for nmtui. School/work networks (eduroam, *802.1X*) ask for method, username, password and the server domain to trust (`l` changes a saved login). Guest Wi-Fi with a web sign-in opens it in the browser (`p` any time; the bar's Wi-Fi icon turns amber with `!`) |
| `bluetooth` | scan, pair + trust + connect, disconnect, remove, battery levels |
| `display` | **Arrange**: a live picture of your screens — `n`/`p` select, arrows move (`HJKL` fine, edges snap together), `+`/`-` scale (the box resizes), `o` rotate, `m` resolution, `e` on/off. Nothing changes until `a`: then keep it (or it reverts in 15 s) and choose whether to remember it for every login. **Details** (Tab): the same as a list, plus mirroring and quick extend/mirror/one-screen layouts |
| `audio` | output / input / per-app volume, default device, move a stream |
| `calendar` | month view, your own events with repeats, plus synced calendars (`c` adds/removes, `S` syncs, `E` opens Evolution) — all shown in the bar's clock popup |
| `keys` | every binding, type to filter |
| `emoji` | type to search, Enter copies |
| `tools` | all utilities; `n` creates your own |

## Wallpapers

`rv open settings` → Theme → **Choose wallpaper…** lists every picture in
`~/Pictures` (any sub-folder) and `wallpapers/`. From the launcher or a
terminal: `rv wallpaper next | prev | random | none | set FILE`.

The repository's pictures are stored with Git LFS, so a clone holds only
stubs; `rv wallpaper fetch` downloads the real files (≈75 MB, checksum
verified) into `~/Pictures/WallPapers`. Any picture you drop in there shows
up too. `none` (a plain colour) uses no memory at all.

## Calendars

Your own events live in `~/.local/share/rv/calendar.json`. Other calendars
are synced **read-only** every 30 minutes (and on `S` in the calendar app):

| source | how to add it (`rv open calendar` → `c`) |
| --- | --- |
| Google Calendar | calendar settings → *Integrate calendar* → **Secret address in iCal format** → paste the link |
| Outlook / Microsoft 365 | Outlook on the web → Settings → Calendar → *Shared calendars* → **Publish a calendar** → copy the ICS link |
| shared / public / school timetable | any `https://` or `webcal://` link ending in `.ics` |
| a downloaded `.ics` file | add the file path (re-read on each sync) |
| Evolution | add *Evolution*: every calendar in it (its Google, Microsoft 365, CalDAV, Exchange accounts and local ones) |

To **create** events that land in Google/Outlook, add the account in
Evolution (`E` in the calendar app opens it), create the event there, and it
syncs back into rv. rv's own events (`a`) stay on this machine.

## Your own utilities

Drop a script in `~/.config/rv/tools/` and it is in the launcher — see
[tools/README.md](tools/README.md). raven-shell tool folders work as they
are (add the folder to `tools.paths`).

## Bash and Vim

- **bash** (`config/bash/rv.bash`): `Ctrl+R` fuzzy history, `Ctrl+T` files,
  `Alt+C` folders (fzf); Up/Down search history by prefix; unknown commands
  suggest the Debian package (command-not-found). With `./install.sh --blesh`
  you also get fish-style grey suggestions as you type (→ accepts). Your own
  prompt is kept; set `RV_PROMPT=1` for rv's.
- **vim** (`config/vim/vimrc`, Vim 9 from `vim-nox`): ALE + python-lsp-server
  for completion, diagnostics, go-to-definition, hover and rename; black (or
  ruff) formatting; `Space r` runs the file (using `.venv` when present).
  Yanks go to the Wayland clipboard.

## Where things live

| change | file |
| --- | --- |
| defaults for everything | `config/rv/defaults.json` (your changes: `~/.config/rv/settings.json`) |
| Hyprland | `config/hypr/rv/*.lua`; personal additions: `~/.config/rv/custom.lua` |
| saved monitor layout | `~/.config/rv/monitors.lua` (written by `rv open display`) |
| the bar and popups | `config/quickshell/rv/*.qml` |
| terminal apps | `tui/*.py` (shared UI in `tui/rvlib.py`) |
| the `rv` command | `bin/rv` (`rv help`) |
| packages | `packages/debian.txt` |

`rv doctor` checks for missing commands.
