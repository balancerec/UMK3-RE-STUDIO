-- UMK3 RE Studio v1.0.1: Mesen 2 experimental DMA/PPU write capture.
-- Read-only callback. CPU PC is contextual, not proof of instruction attribution.
local seq=0
local refs={}
local function get_pc()
    local ok,state=pcall(emu.getState)
    if not ok or type(state)~="table" then return "" end
    local cpu=state.cpu
    if type(cpu)~="table" or type(cpu.pc)~="number" then return "" end
    if type(cpu.k)~="number" then return "" end
    return string.format("$%06X",(cpu.k%256)*65536+(cpu.pc%65536))
end
local function report(address,value)
    seq=seq+1
    emu.log(string.format("UMK3_DMA,0d%d,%s,$%06X,$%02X,write",
        seq,get_pc(),address,value))
end
local function watch(first,last)
    local function cb(address,value) report(address,value) end
    refs[#refs+1]=emu.addMemoryCallback(cb,emu.callbackType.write,
        first,last,emu.cpuType.snes,emu.memType.snesMemory)
end
watch(0x004300,0x00437F)
watch(0x00420B,0x00420B)
watch(0x002115,0x002117)
emu.log("UMK3 CAPTURE START - save log after a graphical transition")
