-- Settings shared with the bar and the terminal apps: the repository's
-- defaults.json overlaid with ~/.config/rv/settings.json (written by
-- `rv settings`). Unknown or malformed values fall back to the default.
local json = require("rv.json")

return function(repoDir)
    local defaults = assert(json.read(repoDir .. "/config/rv/defaults.json"), "cannot read rv defaults.json")
    local home = os.getenv("HOME") or ""
    local configHome = os.getenv("XDG_CONFIG_HOME") or (home .. "/.config")
    local user, problem = json.read(configHome .. "/rv/settings.json")
    if not user and problem ~= "missing" then
        hl.notification.create({ text = "rv: settings.json ignored (" .. problem .. ")", timeout = 8000 })
    end

    local function merge(base, over)
        if type(over) ~= "table" then return base end
        for key, value in pairs(base) do
            local wanted = over[key]
            if type(value) == "table" and type(wanted) == "table" and value[1] == nil then
                merge(value, wanted)
            elseif wanted ~= nil and type(wanted) == type(value) then
                base[key] = wanted
            end
        end
        return base
    end

    local prefs = merge(defaults, user)
    prefs.configHome = configHome .. "/rv"
    return prefs
end
