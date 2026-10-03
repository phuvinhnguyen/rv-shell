-- Minimal JSON decoder: enough for ~/.config/rv/settings.json (objects,
-- arrays, strings, numbers, booleans, null). Returns nil plus a message on
-- malformed input so a typo in the settings file never breaks the session.
local M = {}

local escapes = { b = "\b", f = "\f", n = "\n", r = "\r", t = "\t", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }

local function decode(text)
    local pos = 1

    local function fail(message)
        error({ json = message .. " at byte " .. pos })
    end

    local function skip()
        pos = text:find("[^ \t\r\n]", pos) or #text + 1
    end

    local value

    local function string_value()
        pos = pos + 1
        local parts = {}
        while true do
            local c = text:sub(pos, pos)
            if c == "" then fail("unterminated string") end
            if c == '"' then pos = pos + 1; break end
            if c == "\\" then
                local e = text:sub(pos + 1, pos + 1)
                if e == "u" then
                    local code = tonumber(text:sub(pos + 2, pos + 5), 16) or fail("bad \\u escape")
                    parts[#parts + 1] = utf8.char(code)
                    pos = pos + 6
                else
                    parts[#parts + 1] = escapes[e] or fail("bad escape")
                    pos = pos + 2
                end
            else
                local stop = text:find('["\\]', pos) or #text + 1
                parts[#parts + 1] = text:sub(pos, stop - 1)
                pos = stop
            end
        end
        return table.concat(parts)
    end

    function value()
        skip()
        local c = text:sub(pos, pos)
        if c == "{" then
            pos = pos + 1
            local result = {}
            skip()
            if text:sub(pos, pos) == "}" then pos = pos + 1; return result end
            while true do
                skip()
                if text:sub(pos, pos) ~= '"' then fail("expected key") end
                local key = string_value()
                skip()
                if text:sub(pos, pos) ~= ":" then fail("expected ':'") end
                pos = pos + 1
                result[key] = value()
                skip()
                local sep = text:sub(pos, pos)
                pos = pos + 1
                if sep == "}" then return result end
                if sep ~= "," then fail("expected ',' or '}'") end
            end
        elseif c == "[" then
            pos = pos + 1
            local result = {}
            skip()
            if text:sub(pos, pos) == "]" then pos = pos + 1; return result end
            while true do
                result[#result + 1] = value()
                skip()
                local sep = text:sub(pos, pos)
                pos = pos + 1
                if sep == "]" then return result end
                if sep ~= "," then fail("expected ',' or ']'") end
            end
        elseif c == '"' then
            return string_value()
        elseif text:sub(pos, pos + 3) == "true" then
            pos = pos + 4; return true
        elseif text:sub(pos, pos + 4) == "false" then
            pos = pos + 5; return false
        elseif text:sub(pos, pos + 3) == "null" then
            pos = pos + 4; return nil
        else
            local number = text:match("^-?%d+%.?%d*[eE]?[-+]?%d*", pos)
            if not number or number == "" then fail("unexpected character") end
            pos = pos + #number
            return tonumber(number)
        end
    end

    local result = value()
    skip()
    if pos <= #text then fail("trailing data") end
    return result
end

function M.decode(text)
    local ok, result = pcall(decode, text)
    if ok then return result end
    return nil, type(result) == "table" and result.json or tostring(result)
end

function M.read(path)
    local file = io.open(path, "r")
    if not file then return nil, "missing" end
    local text = file:read("a")
    file:close()
    return M.decode(text)
end

return M
