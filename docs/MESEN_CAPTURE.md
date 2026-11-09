# Assistente de captura Mesen 2

## Objetivo
Capturar escritas nos registradores `$4300–$437F`, `$420B`, `$2115–$2117` com `examples/mesen_dma_capture.lua`.

## Procedimento
1. Abra a Deluxe 2.2 no Mesen 2. Registre o hash SHA-256 da ROM e crie um save state antes da transição gráfica.
2. Em **Debug → Script Window**, execute `examples/mesen_dma_capture.lua`.
3. Entre na seleção de personagem ou inicie uma luta para forçar carregamento gráfico.
4. Pause a emulação e salve o log UTF-8 com linhas `UMK3_DMA`; identifique o estado da tela e o intervalo de frames.
5. Importe no painel **Mesen Capture**, converta, audite e analise na aba **DMA Trace**.
6. Cruze com VRAM/WRAM sincronizadas e rastreie as instruções que geram o buffer.

## PC no Lua
O script chama `emu.getState()` em bloco protegido (`pcall`). Quando `state.cpu.k` e `state.cpu.pc` estiverem disponíveis, forma `$BB:PPPP`. Se indisponíveis, deixa o campo vazio. **PC fornecido por callback pode não coincidir exatamente com o opcode de escrita**; valide no debugger.

## Evidência
- **Observado:** callback de escrita de memória capturado.
- **Inferido:** canal/volume/destino DMA reconstruídos dos registradores.
- **Não confirmado:** rotina produtora, algoritmo de compressão e destino VRAM temporal.

API Lua oficial: https://github.com/SourMesen/Mesen2/blob/master/UI/Debugger/Documentation/LuaDocumentation.json

A captura real ainda requer validação na versão do Mesen instalada no Windows.
