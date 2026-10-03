-- rv: lean Hyprland session for Debian (Hyprland 0.55+, Lua config).
--
-- Every path is resolved from this file's real location, so ~/.config/hypr
-- can be a symlink into the repository. Per-user state lives outside the
-- repository in ~/.config/rv:
--   settings.json   written by `rv settings` (overlaid on config/rv/defaults.json)
--   monitors.lua    written by `rv display`
--   custom.lua      your own hand edits, loaded last (optional)
local source = debug.getinfo(1, "S").source:gsub("^@", "")
local resolver = assert(io.popen("readlink -f -- " .. string.format("%q", source)))
local configFile = assert(resolver:read("*l"), "cannot resolve Hyprland config path")
resolver:close()
local configDir = assert(configFile:match("^(.*)/[^/]+$"))
local repoDir = assert(configDir:match("^(.*)/config/hypr$"), "hyprland.lua must stay in <repo>/config/hypr")

package.path = configDir .. "/?.lua;" .. package.path

local prefs = require("rv.prefs")(repoDir)
local ctx = {
    repo = repoDir,
    rv = string.format("%q", repoDir .. "/bin/rv"),
    prefs = prefs,
    volumeStep = 5,
}

local function optional(path)
    local file = io.open(path, "r")
    if not file then return nil end
    file:close()
    local chunk, problem = loadfile(path)
    if not chunk then
        hl.notification.create({ text = "rv: " .. problem, timeout = 10000 })
        return nil
    end
    local ok, result = pcall(chunk)
    if not ok then
        hl.notification.create({ text = "rv: " .. tostring(result), timeout = 10000 })
        return nil
    end
    return result
end

-- Fallback for any output without a saved rule, then the saved layout.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
for _, monitor in ipairs(optional(prefs.configHome .. "/monitors.lua") or {}) do
    hl.monitor(monitor)
end

require("rv.settings")(ctx)
require("rv.rules")(ctx)
require("rv.keybinds")(ctx)
require("rv.startup")(ctx)

local custom = optional(prefs.configHome .. "/custom.lua")
if type(custom) == "function" then custom(ctx) end
