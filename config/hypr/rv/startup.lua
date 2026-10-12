return function(ctx)
    local rv = ctx.rv
    local function optional(command)
        local name = command:match("^(%S+)")
        return "command -v " .. name .. " >/dev/null && exec " .. command
    end

    hl.on("hyprland.start", function()
        local commands = {
            -- Portals and `notify-send` need the session variables in D-Bus/systemd.
            -- Then restart the portals: ones left over from an earlier session
            -- (another login still running) would open file pickers on that
            -- old, invisible display, so "upload a file" silently fails.
            "dbus-update-activation-environment --systemd WAYLAND_DISPLAY DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE HYPRLAND_INSTANCE_SIGNATURE"
                .. " && systemctl --user restart xdg-desktop-portal-hyprland xdg-desktop-portal-gtk xdg-desktop-portal",
            rv .. " start",
            rv .. " session-helpers",
            optional("gnome-keyring-daemon --start --components=secrets"),
            optional("fcitx5 -d"),
        }
        if ctx.prefs.hypr.nightLight then
            commands[#commands + 1] = optional("gammastep -O 4500")
        end
        for _, command in ipairs(commands) do
            hl.exec_cmd(command)
        end
    end)
end
