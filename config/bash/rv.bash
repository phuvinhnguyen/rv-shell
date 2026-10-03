# rv bash additions. Sourced from ~/.bashrc by install.sh (one guarded line),
# after your own settings, so your prompt and aliases stay yours.
#
#   Ctrl+R      fuzzy history search            (fzf)
#   Ctrl+T      insert a file path              (fzf)
#   Alt+C       cd into a sub-folder            (fzf)
#   →  / End    accept the grey suggestion      (ble.sh, if installed)
#   unknown command → "install it with: apt install …"  (command-not-found)
#
# ble.sh gives fish-style suggestions from your history as you type; it is
# not packaged in Debian, so `install.sh --blesh` fetches it into
# ~/.local/share/blesh. Everything below works without it.

[[ $- == *i* ]] || return 0

_rv_blesh="${XDG_DATA_HOME:-$HOME/.local/share}/blesh/ble.sh"
if [[ -f "$_rv_blesh" && -z "${RV_NO_BLESH:-}" && -z "${BLE_VERSION:-}" ]]; then
    # shellcheck source=/dev/null
    source "$_rv_blesh" --noattach
fi

# History: big, shared between terminals, no duplicates.
HISTSIZE=50000
HISTFILESIZE=100000
HISTCONTROL=ignoreboth:erasedups
HISTIGNORE="ls:ll:cd:pwd:exit:clear:history"
HISTTIMEFORMAT="%F %T  "
shopt -s histappend cmdhist checkwinsize autocd cdspell dirspell globstar 2>/dev/null
PROMPT_COMMAND="history -a${PROMPT_COMMAND:+; $PROMPT_COMMAND}"

# Completion (usually already enabled by Debian's bashrc).
if ! declare -F _completion_loader >/dev/null && [[ -f /usr/share/bash-completion/bash_completion ]]; then
    # shellcheck source=/dev/null
    source /usr/share/bash-completion/bash_completion
fi
bind 'set completion-ignore-case on' 2>/dev/null
bind 'set show-all-if-ambiguous on' 2>/dev/null
bind 'set colored-stats on' 2>/dev/null
bind 'set mark-symlinked-directories on' 2>/dev/null
# Up/Down search history for what is already typed.
bind '"\e[A": history-search-backward' 2>/dev/null
bind '"\e[B": history-search-forward' 2>/dev/null

# fzf: fuzzy history, files and folders.
if command -v fzf >/dev/null; then
    export FZF_DEFAULT_OPTS="--height=40% --layout=reverse --border=rounded --info=inline
        --color=bg+:#201f27,fg+:#e5e1e7,hl:#c2c1ff,hl+:#c2c1ff,pointer:#c2c1ff,prompt:#c2c1ff,border:#34334a"
    if fzf --bash >/dev/null 2>&1; then
        eval "$(fzf --bash)"
    elif [[ -f /usr/share/doc/fzf/examples/key-bindings.bash ]]; then
        # shellcheck source=/dev/null
        source /usr/share/doc/fzf/examples/key-bindings.bash
    fi
fi

# Small conveniences.
alias ls='ls --color=auto --group-directories-first'
alias ll='ls -lh'
alias la='ls -lAh'
alias ..='cd ..'
alias ...='cd ../..'
alias grep='grep --color=auto'
alias py='python3'
alias venv='python3 -m venv .venv && source .venv/bin/activate'
alias activate='source .venv/bin/activate'
export EDITOR="${EDITOR:-vim}"
export VISUAL="${VISUAL:-$EDITOR}"

# A tidy prompt, only if you ask for it (RV_PROMPT=1 in ~/.bashrc before
# this file): folder, git branch, and the exit code when it is not 0.
if [[ "${RV_PROMPT:-}" == 1 ]]; then
    _rv_prompt() {
        local status=$? branch
        branch="$(git symbolic-ref --short HEAD 2>/dev/null)"
        PS1="\[\e[38;2;194;193;255m\]\w\[\e[0m\]${branch:+ \[\e[38;2;142;139;151m\] $branch\[\e[0m\]}"
        ((status)) && PS1+=" \[\e[38;2;255;113;133m\]$status\[\e[0m\]"
        PS1+=" \[\e[38;2;194;193;255m\]❯\[\e[0m\] "
    }
    PROMPT_COMMAND="_rv_prompt${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi

# Attach ble.sh last, after everything else is set up.
if [[ -n "${BLE_VERSION:-}" ]]; then
    bleopt complete_auto_delay=150 2>/dev/null
    ble-attach
fi
unset _rv_blesh
