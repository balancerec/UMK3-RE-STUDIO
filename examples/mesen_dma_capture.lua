-- UMK3 RE Studio v0.8: captura experimental de escritas DMA/PPU no Mesen 2.
-- ABRA em Debug > Script Window e execute. Não modifica RAM, ROM ou registradores.
-- Saída: UMK3_DMA,0d1,,$004300,$01,write
-- Capture o texto do log e importe na aba Mesen Capture Assistant.
-- Base: API emu.addMemoryCallback (Mesen 2); execute e valide em sua versão.
local seq=0
local refs={}
local function report(address,value)
    seq=seq+1
    local line=string.format("UMK3_DMA,0d%d,,$%06X,$%02X,write",seq,address,value)
    emu.log(line)
end
local function watch(startAddr,endAddr)
    local function cb(address,value)
        report(address,value)
        -- Não retornar inteiro; o callback não altera a escrita.
    end
    refs[#refs+1]=emu.addMemoryCallback(cb,emu.callbackType.write,
        startAddr,endAddr,emu.cpuType.snes,emu.memType.snesMemory)
end
watch(0x004300,0x00437F) -- DMA 8 canais
watch(0x00420B,0x00420B) -- MDMAEN
watch(0x002115,0x002117) -- VMAIN, VMADD
emu.log("UMK3 CAPTURE START — registrando escritas DMA/PPU; pause depois da transição")
