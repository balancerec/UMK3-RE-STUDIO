-- UMK3 RE Studio: observa escritas em $7E:3BAE-3BB1 e $7E:1C59 no Mesen 2.
-- Carregue ANTES do reset (Debug > Script Window). Somente leitura: nao altera RAM/ROM.
-- Formato: UMK3_WATCH,<seq>,<frame>,<PC>,$<endereco>,$<valor>
-- O PC e contexto da CPU no instante do callback; nao prova atribuicao de instrucao.
-- ATENCAO: o formato de emu.getState() para a CPU nao foi verificado; get_pc tenta
-- varias chaves e devolve "?" se nenhuma existir (nesse caso cole o getState aqui).
local seq = 0
local refs = {}

local function field(state, ...)
    for _, key in ipairs({...}) do
        local v = state[key]
        if type(v) == "number" then return v end
    end
    local t = state.cpu or (state.snes and state.snes.cpu)
    if type(t) == "table" then
        local v = t.pc
        if type(v) == "number" then return v end
    end
    return nil
end

local function get_pc()
    local ok, st = pcall(emu.getState)
    if not ok or type(st) ~= "table" then return "?" end
    local pc = field(st, "cpu.pc", "snes.cpu.pc")
    local k = st["cpu.k"] or st["snes.cpu.k"] or (type(st.cpu) == "table" and st.cpu.k)
    if type(pc) ~= "number" then return "?" end
    if type(k) == "number" then return string.format("$%02X:%04X", k % 256, pc % 65536) end
    return string.format("$??:%04X", pc % 65536)
end

local function frame()
    local ok, st = pcall(emu.getState)
    if ok and type(st) == "table" and type(st.frameCount) == "number" then return st.frameCount end
    return -1
end

local function report(address, value)
    seq = seq + 1
    emu.log(string.format("UMK3_WATCH,%d,%d,%s,$%06X,$%02X", seq, frame(), get_pc(), address, value))
end

local function watch(first, last)
    refs[#refs + 1] = emu.addMemoryCallback(function(address, value) report(address, value) end,
        emu.callbackType.write, first, last, emu.cpuType.snes, emu.memType.snesMemory)
end

watch(0x7E3BAE, 0x7E3BB1)  -- $3BAE e $3BB0 (16 bits cada)
watch(0x7E1C59, 0x7E1C5A)  -- $1C59
emu.log("UMK3 WATCH START - execute Reset; pause na tela de selecao e salve o log")
