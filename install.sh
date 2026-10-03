#!/usr/bin/env bash
# rv installer for Debian. Run without options to see what it would do.
#
#   ./install.sh                 plan + current status (changes nothing)
#   ./install.sh --apply         link configs into ~/.config, add `rv` to ~/.local/bin
#   ./install.sh --packages      apt install packages/debian.txt [core] (sudo)
#   ./install.sh --extras        … also [extras]
#   ./install.sh --fonts         download a Nerd Font if none is installed
#   ./install.sh --blesh         download ble.sh (fish-style suggestions in bash)
#   ./install.sh --all           packages + fonts + apply
#   ./install.sh --rollback      undo --apply from the latest backup
#
# Everything replaced is moved to ~/.local/state/rv/backups/<time>/ first.
set -euo pipefail

repo="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" && pwd)"
state="${XDG_STATE_HOME:-$HOME/.local/state}/rv"
config="${XDG_CONFIG_HOME:-$HOME/.config}"
bashrc_line="[ -f \"$repo/config/bash/rv.bash\" ] && . \"$repo/config/bash/rv.bash\"  # rv"

# target → source (relative to the repository)
links=(
    "$config/hypr:config/hypr"
    "$config/foot/foot.ini:config/foot/foot.ini"
    "$HOME/.vimrc:config/vim/vimrc"
    "$HOME/.local/bin/rv:bin/rv"
)

bold() { printf '\e[1m%s\e[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
ok() { printf '  \e[32m✓\e[0m %s\n' "$*"; }
warn() { printf '  \e[33m!\e[0m %s\n' "$*"; }

installed() { [[ "$(dpkg-query -W -f='${Status}' "$1" 2>/dev/null)" == "install ok installed" ]]; }

packages() {
    local section="$1"
    awk -v want="[$section]" '/^\[/{on=($0==want); next} on{sub(/#.*/,""); if (NF) print $1}' "$repo/packages/debian.txt"
}

status() {
    bold "Links"
    local entry target source
    for entry in "${links[@]}"; do
        target="${entry%%:*}"; source="$repo/${entry#*:}"
        if [[ "$(readlink -f -- "$target" 2>/dev/null)" == "$(readlink -f -- "$source")" ]]; then ok "$target"
        elif [[ -e "$target" || -L "$target" ]]; then warn "$target exists (would be backed up and replaced)"
        else info "· $target (would be created)"; fi
    done
    grep -qsF "$bashrc_line" "$HOME/.bashrc" && ok "~/.bashrc sources rv.bash" || info "· ~/.bashrc would source config/bash/rv.bash"
    bold "Packages"
    local missing=()
    while read -r pkg; do installed "$pkg" || missing+=("$pkg"); done < <(packages core)
    if ((${#missing[@]})); then warn "missing core: ${missing[*]}"; else ok "all core packages installed"; fi
    missing=()
    while read -r pkg; do installed "$pkg" || missing+=("$pkg"); done < <(packages extras)
    ((${#missing[@]})) && info "· optional extras not installed: ${missing[*]}"
    bold "Other"
    fc-list 2>/dev/null | grep -qi 'Nerd Font' && ok "a Nerd Font is installed" || warn "no Nerd Font (bar icons) — use --fonts"
    [[ -f "${XDG_DATA_HOME:-$HOME/.local/share}/blesh/ble.sh" ]] && ok "ble.sh installed" || info "· ble.sh not installed (optional: --blesh)"
    case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) warn "~/.local/bin is not on PATH (Hyprland calls rv by full path; your shell won't find 'rv')";; esac
}

install_packages() {
    local list
    mapfile -t list < <(packages core; [[ "${1:-}" == extras ]] && packages extras)
    bold "Installing ${#list[@]} packages with apt (sudo)"
    sudo apt-get update
    if ! sudo apt-get install -y --no-install-recommends "${list[@]}"; then
        warn "apt failed. On Debian 13, hyprland/quickshell/hyprpicker need trixie-backports:"
        info "echo 'deb http://deb.debian.org/debian trixie-backports main' | sudo tee /etc/apt/sources.list.d/backports.list"
        info "then: sudo apt-get update && ./install.sh --packages"
        exit 1
    fi
    # PipeWire's Bluetooth plugin must match PipeWire itself. When PipeWire
    # came from backports, plain apt would pick the older plugin from trixie.
    if [[ "$(dpkg-query -W -f='${Version}' pipewire 2>/dev/null)" == *bpo* ]]; then
        sudo apt-get install -y -t trixie-backports libspa-0.2-bluetooth
    else
        sudo apt-get install -y libspa-0.2-bluetooth
    fi
    command -v update-command-not-found >/dev/null && sudo update-command-not-found >/dev/null 2>&1 || true
}

install_fonts() {
    if fc-list | grep -qi 'Nerd Font'; then ok "a Nerd Font is already installed"; return; fi
    bold "Downloading Hack Nerd Font"
    local dir="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/HackNerdFont" tmp
    tmp="$(mktemp -d)"
    curl -fL --progress-bar -o "$tmp/Hack.tar.xz" https://github.com/ryanoasis/nerd-fonts/releases/latest/download/Hack.tar.xz
    mkdir -p "$dir"
    tar -xJf "$tmp/Hack.tar.xz" -C "$dir" --wildcards '*.ttf'
    rm -rf "$tmp"
    fc-cache -f "$dir" >/dev/null
    ok "installed into $dir"
}

install_blesh() {
    local dir="${XDG_DATA_HOME:-$HOME/.local/share}" tmp
    bold "Downloading ble.sh (nightly)"
    tmp="$(mktemp -d)"
    curl -fL --progress-bar -o "$tmp/ble.tar.xz" https://github.com/akinomyoga/ble.sh/releases/download/nightly/ble-nightly.tar.xz
    tar -xJf "$tmp/ble.tar.xz" -C "$tmp"
    rm -rf "$dir/blesh"
    mkdir -p "$dir"
    mv "$tmp"/ble-nightly* "$dir/blesh"
    rm -rf "$tmp"
    ok "installed; open a new terminal for suggestions (→ accepts)"
}

apply() {
    local stamp backup entry target source
    stamp="$(date +%Y%m%d-%H%M%S)"
    backup="$state/backups/$stamp"
    mkdir -p "$backup"
    : >"$backup/manifest"
    bold "Linking configs (backups in $backup)"
    for entry in "${links[@]}"; do
        target="${entry%%:*}"; source="$repo/${entry#*:}"
        if [[ "$(readlink -f -- "$target" 2>/dev/null)" == "$(readlink -f -- "$source")" ]]; then
            ok "$target"; continue
        fi
        mkdir -p "$(dirname -- "$target")"
        if [[ -e "$target" || -L "$target" ]]; then
            mkdir -p "$backup$(dirname -- "$target")"
            mv -- "$target" "$backup$target"
            printf 'moved\t%s\n' "$target" >>"$backup/manifest"
        else
            printf 'created\t%s\n' "$target" >>"$backup/manifest"
        fi
        ln -s -- "$source" "$target"
        ok "$target → $source"
    done
    if ! grep -qsF "$bashrc_line" "$HOME/.bashrc"; then
        cp -a "$HOME/.bashrc" "$backup/bashrc" 2>/dev/null || true
        printf '\n%s\n' "$bashrc_line" >>"$HOME/.bashrc"
        printf 'bashrc\t%s\n' "$HOME/.bashrc" >>"$backup/manifest"
        ok "~/.bashrc now sources config/bash/rv.bash"
    fi
    # Without user-dirs.dirs, Flatpak apps (Zen…) cannot map their Downloads /
    # Documents permission and save through /run/user/…/doc portal paths.
    if [[ ! -f "$config/user-dirs.dirs" ]]; then
        {
            printf '# Standard folders; "$HOME/" switches one off.\n'
            local name dir
            for name in DOWNLOAD:Downloads DOCUMENTS:Documents PICTURES:Pictures DESKTOP:Desktop \
                MUSIC:Music VIDEOS:Videos PUBLICSHARE:Public TEMPLATES:Templates; do
                dir="${name#*:}"
                [[ -d "$HOME/$dir" ]] || dir=""
                printf 'XDG_%s_DIR="$HOME/%s"\n' "${name%%:*}" "$dir"
            done
        } >"$config/user-dirs.dirs"
        printf 'created\t%s\n' "$config/user-dirs.dirs" >>"$backup/manifest"
        ok "~/.config/user-dirs.dirs (standard folders for sandboxed apps)"
    fi
    mkdir -p "$config/rv/tools"
    ok "your tools folder: $config/rv/tools"
    bold "Done"
    info "Log out and pick Hyprland, or reload now with: hyprctl reload && rv restart"
    info "Settings: Super+N   Launcher: Super+A   Keys: Super+/"
}

rollback() {
    local backup line kind target
    backup="$(ls -1d "$state"/backups/*/ 2>/dev/null | tail -n1)"
    [[ -n "$backup" && -f "$backup/manifest" ]] || { warn "no backup found in $state/backups"; exit 1; }
    bold "Rolling back from $backup"
    while IFS=$'\t' read -r kind target; do
        case "$kind" in
            moved)
                [[ -L "$target" ]] && rm -- "$target"
                mv -- "$backup$target" "$target" && ok "restored $target" ;;
            created)
                [[ -L "$target" ]] && rm -- "$target" && ok "removed $target" ;;
            bashrc)
                grep -vF "$bashrc_line" "$target" >"$target.rv-tmp" && mv -- "$target.rv-tmp" "$target"
                ok "removed rv line from $target" ;;
        esac
    done <"$backup/manifest"
    mv -- "$backup" "${backup%/}.rolled-back"
    info "Reload Hyprland (hyprctl reload) or log out to return to your previous setup."
}

case "${1:-}" in
    "") bold "rv installer — nothing changed. Current state:"; status
        printf '\nRun with --apply, --packages, --all … (see the top of %s)\n' "$0" ;;
    --status) status ;;
    --apply) apply ;;
    --packages) install_packages ;;
    --extras) install_packages extras ;;
    --fonts) install_fonts ;;
    --blesh) install_blesh ;;
    --all) install_packages; install_fonts; apply ;;
    --rollback) rollback ;;
    *) sed -n '2,13p' "$0"; exit 2 ;;
esac
