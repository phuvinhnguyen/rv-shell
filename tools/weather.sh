#!/usr/bin/env bash
# name: Weather
# icon: 󰖕
# description: Forecast from wttr.in (set RV_WEATHER_CITY to pin a place)
# terminal: hold
# keywords: forecast rain temperature
set -euo pipefail
curl -fsS "https://wttr.in/${RV_WEATHER_CITY:-}?F" || echo "wttr.in is unreachable right now."
