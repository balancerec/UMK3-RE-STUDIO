-- UMK3-RE-STUDIO / Mesen Bridge — protótipo v0.1 (Lua MesenCE)
-- Observar SOMENTE: nao faz patch, write, reset nem altera o estado da ROM.
-- Carregue no debugger do MesenCE > Script Window.
-- Opcional: para salvar JSONL, habilite I/O nas restricoes do Script Window e
-- defina um caminho local gravavel em OUTPUT_PATH.
-- Sem permissao de I/O: emu.log apresenta eventos no Script Window (historico limitado).
local SESSION_ID = "exp001_run01"
local OUTPUT_PATH = "" -- ex.: "C:/UMK3/evidencias/exp001_run01.jsonl"
local MAX_EVENTS = 20000

-- CPU Exec usa snesMemory: endereco do barramento completo 24 bits.
-- WRAM Write usa snesWorkRam: offset fisico de 17 bits, SEM banco $7E.
local cpu_points = {0x86A353, 0x86A355, 0x86A385, 0x86A733, 0x86A738, 0x86A73A, 0x86A7A8}
local wram_points = {0x0C0E, 0x3A50, 0x36D0, 0x52C8, 0x1C59}

assert(type(emu) == "table", "Mesen Lua API nao encontrada")
assert(emu.callbackType and emu.callbackType.exec and emu.callbackType.write, "Callbacks nao encontrados")
assert(emu.memType and emu.memType.snesMemory and emu.memType.snesWorkRam, "Tipos de memoria indisponiveis")
local output = nil
if OUTPUT_PATH ~= "" then
  if io == nil then
    error("I/O Lua desabilitado. Ative Script Window > Settings > Restrictions > Allow access to I/O and OS functions; ou deixe OUTPUT_PATH vazio.")
  end
  local handle, err = io.open(OUTPUT_PATH, "a")
  if not handle then error("Nao foi possivel abrir arquivo JSONL: " .. tostring(err)) end
  output = handle
end

local seq = 0
local function escaped(v)
  v = tostring(v)
  return '"' .. v:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\t", "\\t") .. '"'
end
local function encode_table(tbl)
  if type(tbl) ~= "table" then return "null" end
  local parts = {}
  for key, value in pairs(tbl) do
    if type(key) == "string" and (type(value) == "string" or type(value) == "number" or type(value) == "boolean") then
      local v = type(value) == "string" and escaped(value) or tostring(value)
      parts[#parts+1] = escaped(key) .. ":" .. v
    end
  end
  return "{" .. table.concat(parts, ",") .. "}"
end
local function record(kind, address, callback_value, space)
  if seq >= MAX_EVENTS then return end
  seq = seq + 1
  local state = emu.getCpuState()
  -- O callback pode ocorrer antes da operacao: callback_value nao e o valor
  -- final confirmado. A semantica de PC/registradores requer validacao em MesenCE.
  local line = '{"schema_version":"0.1","session_id":' .. escaped(SESSION_ID)
    .. ',"seq":' .. seq .. ',"kind":' .. escaped(kind)
    .. ',"cpu":"snes","address":' .. escaped(string.format("%06X",address))
    .. ',"memory_space":' .. escaped(space)
    .. ',"callback_value":' .. tostring(callback_value or 0)
    .. ',"value_before":null,"value_after":null,"value_after_status":"unknown"'
    .. ',"callback_phase":"unverified","registers":' .. encode_table(state) .. '}'
  if output then
    output:write(line, "\n")
    output:flush()
  else
    emu.log(line)
  end
end

for _, addr in ipairs(cpu_points) do
  local watched = addr
  emu.addMemoryCallback(function(address, value)
    record("cpu_execute", address, value, "CPU")
  end, emu.callbackType.exec, watched, watched, emu.memType.snesMemory)
end
for _, addr in ipairs(wram_points) do
  local watched = addr
  emu.addMemoryCallback(function(address, value)
    record("memory_write", address, value, "WRAM")
  end, emu.callbackType.write, watched, watched, emu.memType.snesWorkRam)
end
emu.log("UMK3 Mesen Bridge v0.1 ativo: " .. SESSION_ID ..
  " | observadores CPU=" .. #cpu_points .. " WRAM=" .. #wram_points ..
  " | destino=" .. (output and OUTPUT_PATH or "Script Window"))
