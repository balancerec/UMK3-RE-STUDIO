# Changelog

## 1.0.1 — Estabilização e consolidação
- Corrigido erro de persistência ao salvar `dma_trace` em projetos SQLite.
- Corrigido fetch de operandos e próximo PC com wrap no PBR para desmontagem 65C816.
- Aplicada a regra de wrap aos blocos e referências cruzadas.
- Corrigido rastreamento conservador do flag E após PLP/RTI.
- Exportação MLB inclui símbolos além do limite de 2.000 exibido na interface.
- Script Lua experimental passa a tentar capturar PBR:PC via `emu.getState()`.
- Integrado laboratório v1.0 de hipóteses RLE/PackBits, sem declaração de codec UMK3.
- Adicionados testes de regressão e documentação técnica.

## 1.0 — Graphics Decompression Research Lab
Laboratório de formatos experimentais, perfis de bytes e comparador ROM × VRAM.

## 0.1–0.9
Evolução do parser SNES, disassembler, SQLite, Character Mapper, Graphics Explorer, DMA Trace, Mesen Capture e correlação.
