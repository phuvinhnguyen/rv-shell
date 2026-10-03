#!/usr/bin/env bash
# name: QR from clipboard
# icon: 󰐲
# description: Show the copied text as a QR code in the terminal
# terminal: hold
# keywords: qrcode share phone link
set -euo pipefail

command -v qrencode >/dev/null || { echo "Install qrencode:  sudo apt install qrencode"; exit 1; }
text="$(wl-paste --no-newline --type text 2>/dev/null || true)"
[[ -n "$text" ]] || { echo "The clipboard has no text."; exit 1; }
qrencode -t ansiutf8 -m 2 -- "$text"
printf '\n%s\n' "${text:0:200}"
