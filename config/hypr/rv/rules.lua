return function(ctx)
    -- Terminal apps opened by `rv open <name>` use the app id rv.<name>.
    local sizes = {
        settings = "960 640", display = "900 600", wifi = "720 520", bluetooth = "720 520",
        audio = "760 520", calendar = "820 600", keys = "860 640", emoji = "560 520",
        tools = "720 520", monitor = "1100 700", power = "420 300",
    }
    for name, size in pairs(sizes) do
        hl.window_rule({ match = { class = "^rv\\." .. name .. "$" }, float = true, size = size, center = true })
    end
    -- Anything else started through `rv term --float`.
    hl.window_rule({ match = { class = "^rv\\.float$" }, float = true, size = "860 560", center = true })

    hl.window_rule({ match = { float = true, xwayland = false }, center = true })

    local floating = "pavucontrol|org\\.pulseaudio\\.pavucontrol|nm-connection-editor|blueman-manager"
        .. "|file-roller|org\\.gnome\\.FileRoller|imv|feh|mpv|zenity|yad|xdg-desktop-portal-gtk"
    hl.window_rule({ match = { class = floating }, float = true })

    for _, title in ipairs({
        "(Select|Open)( a)? (File|Folder)(s)?",
        "File (Operation|Upload)( Progress)?",
        ".* Properties",
        "Save As",
    }) do
        hl.window_rule({ match = { title = title }, float = true })
    end

    local pip = { title = "Picture(-| )in(-| )[Pp]icture" }
    hl.window_rule({ match = pip, float = true, pin = true, keep_aspect_ratio = true, move = "68% 65%" })

    -- The shell's own surfaces: no slide animation for popups and the OSD.
    hl.layer_rule({ match = { namespace = "^rv-(launcher|osd|popup)$" }, no_anim = true })
end
