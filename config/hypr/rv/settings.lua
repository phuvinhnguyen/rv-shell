return function(ctx)
    local p = ctx.prefs
    local h = p.hypr
    local t = p.theme

    local function rgb(hex) return (hex:gsub("^#", "")) end

    local environment = {
        QT_QPA_PLATFORM = "wayland;xcb",
        QT_WAYLAND_DISABLE_WINDOWDECORATION = "1",
        GDK_BACKEND = "wayland,x11",
        SDL_VIDEODRIVER = "wayland,x11",
        ELECTRON_OZONE_PLATFORM_HINT = "auto",
        MOZ_ENABLE_WAYLAND = "1",
        XDG_CURRENT_DESKTOP = "Hyprland",
        XDG_SESSION_TYPE = "wayland",
        XDG_SESSION_DESKTOP = "Hyprland",
        _JAVA_AWT_WM_NONREPARENTING = "1",
        XCURSOR_SIZE = "24",
    }
    -- No CLUTTER_BACKEND: forcing "wayland" makes clutter-gtk apps (Evolution,
    -- GNOME Contacts/Maps) hang on start; clutter-gtk picks the right backend.
    for name, value in pairs(environment) do
        hl.env(name, value)
    end

    local layout = (h.layout == "dwindle" or h.layout == "master") and h.layout or "scrolling"

    hl.config({
        general = {
            layout = layout,
            resize_on_border = true,
            extend_border_grab_area = 15,
            gaps_workspaces = 8,
            gaps_in = h.gapsIn,
            gaps_out = h.gapsOut,
            border_size = h.border,
            col = {
                active_border = "rgba(" .. rgb(t.accent) .. "e6)",
                inactive_border = "rgba(c8c5d122)",
            },
        },
        scrolling = {
            direction = "right",
            fullscreen_on_one_column = true,
            focus_fit_method = 0,
            column_width = 1.0,
            follow_focus = true,
            follow_min_visible = 0.8,
            explicit_column_widths = "0.35, 0.5, 0.65, 1.0",
        },
        dwindle = { preserve_split = true },
        decoration = {
            rounding = h.rounding,
            -- Blur and shadows cost GPU time and texture memory on every
            -- frame; both are off by default and toggled in `rv settings`.
            blur = {
                enabled = h.blur,
                size = 6,
                passes = 2,
                new_optimizations = true,
                xray = true,
                popups = false,
            },
            shadow = {
                enabled = h.shadow,
                range = 12,
                render_power = 3,
                color = "rgba(00000066)",
            },
        },
        animations = { enabled = h.animations },
        input = {
            kb_layout = h.kbLayout,
            kb_options = h.kbOptions,
            repeat_delay = h.repeatDelay,
            repeat_rate = h.repeatRate,
            sensitivity = h.sensitivity,
            focus_on_close = 1,
            touchpad = {
                natural_scroll = h.naturalScroll,
                disable_while_typing = true,
                scroll_factor = 0.3,
            },
        },
        binds = { scroll_event_delay = 0 },
        cursor = { hotspot_padding = 1 },
        gestures = {
            workspace_swipe_distance = 700,
            workspace_swipe_cancel_ratio = 0.15,
            workspace_swipe_create_new = true,
        },
        misc = {
            vrr = 1,
            disable_hyprland_logo = true,
            disable_splash_rendering = true,
            force_default_wallpaper = 0,
            background_color = "rgb(" .. rgb(t.background) .. ")",
            animate_manual_resizes = false,
            animate_mouse_windowdragging = false,
            on_focus_under_fullscreen = 2,
            focus_on_activate = true,
            allow_session_lock_restore = true,
            middle_click_paste = false,
            mouse_move_enables_dpms = true,
            key_press_enables_dpms = true,
        },
        group = {
            col = {
                border_active = "rgba(" .. rgb(t.accent) .. "e6)",
                border_inactive = "rgba(c8c5d122)",
            },
            groupbar = {
                font_family = t.font,
                font_size = 12,
                height = 18,
                gradients = false,
                text_color = "rgb(" .. rgb(t.text) .. ")",
                col = {
                    active = "rgba(" .. rgb(t.accent) .. "66)",
                    inactive = "rgba(" .. rgb(t.surface) .. "cc)",
                },
            },
        },
        debug = { error_position = 1 },
    })

    -- Short, calm animations: quick enough to feel instant.
    hl.curve("rvOut", { type = "bezier", points = { { 0.23, 1 }, { 0.32, 1 } } })
    hl.animation({ leaf = "global", enabled = true, speed = 5, bezier = "rvOut" })
    hl.animation({ leaf = "windows", enabled = true, speed = 3.5, bezier = "rvOut", style = "popin 90%" })
    hl.animation({ leaf = "fade", enabled = true, speed = 3, bezier = "rvOut" })
    hl.animation({ leaf = "layers", enabled = true, speed = 3, bezier = "rvOut", style = "fade" })
    hl.animation({ leaf = "workspaces", enabled = true, speed = 4, bezier = "rvOut", style = "slidevert" })

    hl.gesture({ fingers = 3, direction = "vertical", action = "workspace" })
    hl.gesture({ fingers = 3, direction = "horizontal", scale = 2.0, action = "scroll_move" })
end
