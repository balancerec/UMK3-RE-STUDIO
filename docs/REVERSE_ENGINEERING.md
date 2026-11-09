# Dossiê técnico de engenharia reversa

## Evidências do UMK3 Deluxe 2.2
- ROM comercial analisada em capturas anteriores: 8 MiB, ExHiROM, map byte `$35`, checksum armazenado `DE7A` e complemento `2185`.
- Hook em ROM offset `0x08A53C` / CPU `$C8:A53C`: `JML $D0:5E62`, destino físico candidato `0x105E62`.
- Dois campos candidatos para ID de personagem: WRAM `$7E:36D0` e `$7E:52C8`.
- Human Smoke está identificado como captura **provável**, não confirmação inequívoca.
- O ID `0x19` não pode ser atribuído a Idels sem captura que o comprove.
- Testes RLE/PackBits em janelas da ROM/VRAM **não demonstraram** um formato proprietário.

## Protocolo de evidências
1. Registrar SHA-256 da ROM e offsets CPU/arquivo.
2. Distinguir observado, inferido e desconhecido.
3. Salvar save state e dump sincronizado no ponto de observação.
4. Reproduzir com segunda captura.
5. Executar breakpoints de escrita nas variáveis candidatas.
6. Só batizar funções/estruturas quando houver rastreamento e referências suficientes.

## Critérios para confirmar um codec gráfico
Identificar a rotina de entrada na ROM, capturar saída em WRAM/VRAM sincronizada, implementar decodificador independente que produza bytes exatos e repetir em múltiplos recursos.

## Referências semânticas, não equivalentes de binário
- https://github.com/RetailGameSourceCode/UltimateMortalKombat3 — código parcial de outra plataforma.
- https://github.com/MaryNCRT/Ultimate-Mortal-Kombat-3-iOS-Decompiled — engine iOS, IDs não necessariamente iguais aos da versão SNES.
