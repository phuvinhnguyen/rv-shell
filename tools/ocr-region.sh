#!/usr/bin/env bash
# name: Text from screen (OCR)
# icon: 󱄽
# description: Select an area; its text is copied to the clipboard
# terminal: no
# keywords: ocr tesseract copy text recognise
set -euo pipefail

notify() { if command -v notify-send >/dev/null; then notify-send -a rv "$@" || true; fi; }
for cmd in grim slurp tesseract wl-copy; do
    command -v "$cmd" >/dev/null || { notify -u critical "OCR unavailable" "Install grim, slurp and tesseract-ocr"; exit 1; }
done
geometry="$(slurp)" || exit 0
text="$(grim -g "$geometry" - | tesseract - - -l "${RV_OCR_LANG:-eng}" 2>/dev/null)"
if [[ -z "${text//[[:space:]]/}" ]]; then
    notify "No text found"
    exit 0
fi
printf '%s' "$text" | wl-copy
notify "Text copied" "${text:0:120}"
