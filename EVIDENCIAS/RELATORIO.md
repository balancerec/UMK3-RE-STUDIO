# UMK3 Deluxe 2.2 — v0.6 DMA / Graphics Compression Analyzer

SHA-256 da ROM analisada: `f512ef861f0df2dbb8f9563fb5f3b01ab70b7048ac329a9262ff3d34ca487bdd`

Análise estática de assinaturas de escrita em registradores PPU/DMA. **Não é um trace de execução DMA**. O filtro exige bit CODE do CDL no primeiro byte da assinatura, mas não comprova fronteira de instrução ou estado do registrador DBR.

- 26 candidatos com bit CODE do CDL.
- 67 candidatos por assinaturas em toda a ROM (incluindo possíveis falsos positivos em dados).
- Contagem por registrador: {"HDMAEN": 2, "VMAIN": 5, "VMADDL": 7, "MDMAEN": 9, "CGADD": 2, "VMDATAL": 1}.
- Exemplo encontrado em `0x049DA3`? Consultar CSV para offsets exatos; não presumir contexto da instrução.

A comparação pontual dos primeiros 4096 bytes da VRAM com a captura WRAM anterior (janela 32 bytes e mínimo de 12 valores distintos) encontrou 17 janelas elegíveis e nenhuma correspondência exata. Os dumps não foram comprovadamente obtidos no mesmo frame e, portanto, esse resultado não permite concluir nada sobre codec ou transferência.

## Próxima evidência necessária

No Mesen 2, durante o carregamento do personagem, registre PC, DBR, `$420B`, configuração dos canais `$4300–$437F`, `$2115–$2119` e uma captura sincronizada da WRAM e VRAM. Só depois relacione origem comprimida, buffer de saída e destino.
