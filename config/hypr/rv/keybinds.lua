-- Key bindings. The layout follows raven-shell's standalone config, with the
-- shell surfaces mapped onto rv. `rv keys` (Super+/) lists everything bound.
return function(ctx)
    local rv = ctx.rv
    local function run(command) return hl.dsp.exec_cmd(command) end
    local function bind(keys, action, options, description)
        options = options or {}
        options.description = description
        hl.bind(keys, action, options)
    end

    -- Shell surfaces.
    bind("SUPER + A", run(rv .. " launcher"), nil, "Launcher: apps, tools and commands")
    bind("SUPER + SHIFT + A", run(rv .. " launcher tools"), nil, "Launcher: utilities")
    bind("SUPER + V", run(rv .. " launcher clipboard"), nil, "Launcher: clipboard history")
    bind("SUPER + N", run(rv .. " open settings"), nil, "Settings")
    bind("SUPER + SHIFT + N", run(rv .. " notifications"), nil, "Notification list")
    bind("CTRL + ALT + C", run(rv .. " notifications clear"), { locked = true }, "Notifications: clear all")
    bind("SUPER + K", run(rv .. " bar toggle"), nil, "Bar: show / hide")
    bind("SUPER + L", run(rv .. " lock"), nil, "Lock the session")
    bind("SUPER + SHIFT + L", run(rv .. " power suspend"), { locked = true }, "Suspend")
    bind("SUPER + ESCAPE", run(rv .. " power menu"), nil, "Power menu")
    bind("SUPER + SHIFT + P", run(rv .. " power-mode cycle"), nil, "Power mode: saver / balanced / performance")
    bind("SUPER + SLASH", run(rv .. " open keys"), nil, "Keybinding cheatsheet")
    bind("SUPER + P", run(rv .. " open display"), nil, "Displays")
    bind("SUPER + SHIFT + E", run(rv .. " open emoji"), nil, "Emoji picker")
    bind("CTRL + SHIFT + ESCAPE", run(rv .. " open monitor"), nil, "System monitor")
    bind("switch:Lid Switch", run(rv .. " lock"), { locked = true }, "Lid closed: lock")
    bind("CTRL + SUPER + SHIFT + R", run(rv .. " stop"), { release = true }, "Shell: quit")
    bind("CTRL + SUPER + ALT + R", run(rv .. " restart"), { release = true }, "Shell: restart")

    -- Applications (resolved from `rv settings` → Apps).
    bind("SUPER + T", run(rv .. " app terminal"), nil, "Terminal")
    bind("SUPER + RETURN", run(rv .. " app terminal"), nil, "Terminal")
    bind("SUPER + B", run(rv .. " app browser"), nil, "Browser")
    bind("SUPER + C", run(rv .. " app editor"), nil, "Editor")
    bind("SUPER + E", run(rv .. " app files"), nil, "File manager")

    -- Screenshots and pickers.
    bind("SUPER + SHIFT + S", run(rv .. " screenshot region"), nil, "Screenshot: region")
    bind("PRINT", run(rv .. " screenshot full"), nil, "Screenshot: full screen")
    bind("SUPER + SHIFT + C", run("hyprpicker -a"), nil, "Colour picker")

    -- Hardware keys.
    bind("XF86MonBrightnessUp", run("brightnessctl -q set 5%+ && " .. rv .. " osd brightness"),
        { locked = true, repeating = true }, "Brightness up")
    bind("XF86MonBrightnessDown", run("brightnessctl -q set 5%- && " .. rv .. " osd brightness"),
        { locked = true, repeating = true }, "Brightness down")
    bind("XF86AudioRaiseVolume",
        run("wpctl set-mute @DEFAULT_AUDIO_SINK@ 0; wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ " .. ctx.volumeStep .. "%+"),
        { locked = true, repeating = true }, "Volume up")
    bind("XF86AudioLowerVolume",
        run("wpctl set-volume @DEFAULT_AUDIO_SINK@ " .. ctx.volumeStep .. "%-"),
        { locked = true, repeating = true }, "Volume down")
    bind("XF86AudioMute", run("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true }, "Mute")
    bind("XF86AudioMicMute", run("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true }, "Mute microphone")
    bind("XF86AudioPlay", run(rv .. " media toggle"), { locked = true }, "Media: play / pause")
    bind("XF86AudioNext", run(rv .. " media next"), { locked = true }, "Media: next")
    bind("XF86AudioPrev", run(rv .. " media previous"), { locked = true }, "Media: previous")
    bind("XF86AudioStop", run(rv .. " media stop"), { locked = true }, "Media: stop")

    -- Workspaces 1-10 (ten is the 0 key). Ctrl selects workspace "groups":
    -- Ctrl+Super+N jumps to the same slot in group N (N1..N10).
    local function grouped(key, move)
        return function()
            local active = hl.get_active_workspace()
            local id = active and tonumber(active.id) or 1
            local slot = id % 10
            if slot == 0 then slot = 10 end
            local target = (key - 1) * 10 + slot
            if move then
                hl.dispatch(hl.dsp.window.move({ workspace = target }))
            else
                hl.dispatch(hl.dsp.focus({ workspace = target }))
            end
        end
    end
    for workspace = 1, 10 do
        local key = workspace % 10
        bind("SUPER + " .. key, hl.dsp.focus({ workspace = workspace }), nil, "Workspace " .. workspace)
        bind("SUPER + SHIFT + " .. key, hl.dsp.window.move({ workspace = workspace }), nil, "Move window to workspace " .. workspace)
        bind("CTRL + SUPER + " .. key, grouped(workspace, false), nil, "Workspace group " .. workspace)
        bind("CTRL + SUPER + SHIFT + " .. key, grouped(workspace, true), nil, "Move window to group " .. workspace)
    end
    bind("SUPER + mouse_down", hl.dsp.focus({ workspace = "e+1" }), nil, "Next workspace")
    bind("SUPER + mouse_up", hl.dsp.focus({ workspace = "e-1" }), nil, "Previous workspace")
    bind("SUPER + COMMA", hl.dsp.focus({ workspace = "-1" }), { repeating = true }, "Previous workspace")
    bind("SUPER + PERIOD", hl.dsp.focus({ workspace = "+1" }), { repeating = true }, "Next workspace")
    bind("SUPER + S", hl.dsp.workspace.toggle_special(), nil, "Scratchpad: show / hide")
    bind("SUPER + SHIFT + X", hl.dsp.window.move({ workspace = "special" }), nil, "Scratchpad: send window")

    -- Windows and groups.
    bind("SUPER + Q", hl.dsp.window.close(), nil, "Close window")
    bind("SUPER + F", hl.dsp.window.fullscreen({ mode = "fullscreen" }), nil, "Fullscreen")
    bind("SUPER + W", hl.dsp.window.float(), nil, "Toggle floating")
    bind("SUPER + TAB", hl.dsp.layout("toggleoverview"), nil, "Overview (scrolling layout)")
    bind("ALT + TAB", hl.dsp.window.cycle_next(), { repeating = true }, "Next window")
    bind("SHIFT + ALT + TAB", hl.dsp.window.cycle_next({ next = false }), { repeating = true }, "Previous window")
    bind("CTRL + ALT + TAB", hl.dsp.group.next(), { repeating = true }, "Next tab in group")
    bind("CTRL + SHIFT + ALT + TAB", hl.dsp.group.prev(), { repeating = true }, "Previous tab in group")
    bind("SUPER + G", hl.dsp.group.toggle(), nil, "Group: toggle")
    bind("SUPER + U", hl.dsp.window.move({ out_of_group = true }), nil, "Group: take window out")
    bind("SUPER + SHIFT + G", hl.dsp.group.lock_active({ action = "toggle" }), nil, "Group: lock")
    bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true }, "Hold to move window")
    bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true }, "Hold to resize window")

    local directions = { LEFT = "l", RIGHT = "r", UP = "u", DOWN = "d" }
    for key, direction in pairs(directions) do
        bind("SUPER + " .. key, hl.dsp.focus({ direction = direction }), nil, "Focus " .. key:lower())
        bind("SUPER + SHIFT + " .. key, hl.dsp.window.move({ direction = direction }), nil, "Move window " .. key:lower())
    end

    -- Keyboard pointer: Ctrl+Super+arrows move it, add Shift to resize the window.
    local steps = {
        LEFT = { -8, 0, "left" }, DOWN = { 0, 8, "down" },
        UP = { 0, -8, "up" }, RIGHT = { 8, 0, "right" },
    }
    for key, step in pairs(steps) do
        bind("CTRL + SUPER + " .. key, function()
            local position = hl.get_cursor_pos()
            if position ~= nil then
                hl.dispatch(hl.dsp.cursor.move({ x = position.x + step[1], y = position.y + step[2] }))
            end
        end, { repeating = true }, "Cursor: move " .. step[3])
        bind("CTRL + SUPER + SHIFT + " .. key,
            hl.dsp.window.resize({ x = step[1], y = step[2], relative = true }),
            { repeating = true }, "Window: resize " .. step[3])
    end
    local function click(button)
        return function()
            for _, state in ipairs({ "down", "up" }) do
                hl.dispatch(hl.dsp.send_key_state({ mods = "", key = "mouse:" .. button, state = state }))
            end
        end
    end
    bind("CTRL + SUPER + RETURN", click(272), nil, "Cursor: left click")
    bind("CTRL + SUPER + SHIFT + RETURN", click(273), nil, "Cursor: right click")
end
