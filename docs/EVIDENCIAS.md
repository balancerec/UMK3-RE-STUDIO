# Catálogo de evidências — Hidden Roster Engine

ROM: Ultimate Mortal Kombat 3 Deluxe 2.2, 8 MiB, SHA-256 `f512ef861f0df2dbb8f9563fb5f3b01ab70b7048ac329a9262ff3d34ca487bdd` (**confirmado** em 2026-11-09 contra o arquivo `.sfc` fornecido).

Classes: **CONFIRMADO** (bytes da ROM ou execução observada), **INFERIDO** (dedução direta de CONFIRMADO), **HIPÓTESE**, **NÃO VERIFICADO**.
"Estático" significa leitura da ROM, não execução. Os "observados no Mesen" vêm do prompt do projeto; esta auditoria não executou a ROM.

## E-001 — Mapeamento ExHiROM (correção de bug no Studio)
- **Evidência:** 11 sequências de bytes do disassembly observado (`$86:A1F6`, `$86:A383`, `$86:A3B3`, `$86:A726`, `$86:A7A6`, `$86:A164`, `$86:A73F`, `$88:94EC`, `$88:980F`, `$80:83F2`, `$80:86B1`) e `$C4:A362` conferem byte a byte com `offset = (banco & 0x3F) << 16 | endereço` para `$80–$BF:8000–FFFF` e `$C0–$FF`.
- **Antes:** `core.cpu_to_file` mandava `$80–$BF` para a metade alta (`0x600000+`). Qualquer endereço `$80–$BF` lia zeros ou dados errados.
- **Agora:** `$80–$BF` e `$C0–$FF` → 4 MiB baixos; `$40–$7D` e `$00–$3F:8000+` → 4 MiB altos (**conforme a especificação ExHiROM**; não verificado por execução nesta ROM).
- **Classe:** CONFIRMADO (baixos) / INFERIDO pela especificação (altos). Teste: `tests/test_core.py::test_mapping_exhirom`.

## E-002 — Duas metades com código diferente
- As metades baixa (`0x000000–0x3FFFFF`) e alta (`0x400000–0x7FFFFF`) são só ~4,1% idênticas byte a byte; nenhum banco de 64 KiB é igual.
- Vetor de reset `$83D7` (idêntico nas duas): em `$00:83D7` (alta) o código executa `SEI; CLD; CLC; XCE; REP #$30; …; JML $80:83F2` (bytes `5C F2 83 80`). **O boot passa para a metade baixa** em `$80:83F2` (a limpeza de WRAM de `$80:83F2` está nos 239 primeiros bytes idênticos).
- **Classe:** CONFIRMADO (estático). **Implicação:** o mesmo endereço de banco pode existir em dois lugares físicos diferentes; ver E-008.

## E-003 — Tabela `$86:A207` (índice → ID)
- Offset `0x06A207`, 24 bytes: `18 13 05 02 03 10 17 01 00 11 FF 15 04 09 07 0F 14 12 08 0A 06 0E 0D 0C`.
- Índice `0x03` → `02` (Jax) e `0x0A` → `FF`, como no prompt. **CONFIRMADO.**
- **Comprimento 24:** o byte seguinte (`A0 02 00 A9 …`) decodifica como código (`LDY #$0002`…) e as quatro tabelas de navegação também têm 24 bytes. **INFERIDO.**
- IDs de `00` a `1B` ausentes da tabela visível: `0B` (Sheeva), `16` (Human Smoke), `19` (Idels), `1A` (Motaro), `1B` (Shao Kahn), exatamente os cinco personagens atribuídos ao slot oculto. **CONFIRMADO** (estático); a interpretação de que só podem aparecer via `$1C59` é **INFERIDO**.
- Nomes: só os IDs com evidência (prompt + `characters.csv`) têm nome. `00 04 06 07 08 0D 0E 0F 11 12 15` ficam **NÃO VERIFICADO**. A ordem do arcade UMK3 sugere nomes para eles, mas isso é **HIPÓTESE** e não foi adotada.

## E-004 — Tabelas de navegação
- `$86:A6C6`, `A6DE`, `A6F6`, `A70E` (24 bytes cada, `0x06A6C6…`), selecionadas por `BIT #$0800/#$0400/#$0200/#$0100` sobre `$0A` em `$86:A383–A3E5` (**CONFIRMADO**, código lido da ROM).
- Mapeamento para Cima/Baixo/Esquerda/Direita: pelo layout do registrador de joypad (bits 11–8) e pelos dados (a tabela `A6C6` só reduz de linha). **INFERIDO.**
- Layout: linhas de 7, 7, 5 e 5 posições (índices 0–6, 7–13, 14–18, 19–23); o slot oculto `0x0A` é a coluna 3 da linha 2 e é alvo de "cima" a partir do índice `0x10`. **INFERIDO** das tabelas.
- Parâmetros `X`/`Y` passados a `$86:A726` (`#$0000/#$FFC0`, `#$0000/#$0040`, `#$FFCE/#$0000`, …): função **NÃO VERIFICADO**.

## E-005 — Escritas estáticas em `$7E:1C59`
Varredura por padrão de bytes (`STA/STZ/INC/…` abs ou long `$7E`), **sem decodificação**, portanto com possíveis falsos positivos:

| CPU | Padrão | Valor | Classe |
|---|---|---|---|
| `$C4:A309` | `STZ $1C59` (precedido por `STZ $1C57`) | 0 | CONFIRMADO (estático) |
| `$C4:A349` | `LDA #$001B; STA $1C59` | Shao Kahn | CONFIRMADO (estático) |
| `$C4:A36A` | `LDA #$001A; STA $1C59` | Motaro | CONFIRMADO (estático) |
| `$FF:FE41` | `LDA #$000B; STA $1C59` | Sheeva | CONFIRMADO (estático) |
| `$FF:FE67` | `LDA #$0016; STA $1C59` | Human Smoke | CONFIRMADO (estático) |
| `$FF:FE8D` | `LDA #$0019; STA $1C59` | Idels | CONFIRMADO (estático) |
| `$E6:A157` (`ASL`), `$E9:0BA3` e `$FE:FDB2` (`TRB`) | padrão de bytes | — | **NÃO VERIFICADO** (contexto parece dado) |

Não há `STA long $7E:1C59`. Escritas indiretas, indexadas, `MVN/MVP` e DMA **não são detectadas** por essa varredura.

## E-006 — `$C4:A2FC–A385`
```
C4:A306 STZ $1C57      C4:A328 LDA $3BAE ; ORA $3BB0 ; BEQ $A385   (sai se ambos 0)
C4:A309 STZ $1C59      C4:A330 LDA #1 ; JSL $88C637 ; LDA $36C6 ; BEQ $A330   (espera $36C6 != 0)
C4:A341 LDA $3BAE ; BEQ $A362  → se $3BAE != 0: $1C59 = $1B (Shao Kahn)
C4:A362 LDA $3BB0 ; BEQ $A383  → se $3BB0 != 0: $1C59 = $1A (Motaro)
```
**CONFIRMADO** (estático). O papel de `JSL $88C637` com `A=1` e de `$36C6` **NÃO VERIFICADO**.

## E-007 — `$FF:FE3B–FE8D` (Sheeva, Human Smoke, Idels)
Em `FF:FE3B`, `FE61` e `FE87` há `LDA $3BAE` seguido **diretamente** de `LDA #imm; STA $1C59`, sem desvio no fluxo linear. O `LDA $3BAE` não condiciona essas escritas na leitura linear (o `LDA #imm` seguinte sobrescreve os flags). **Isto corrige a hipótese inicial de que `$3BAE` condicionaria os três.** Hipóteses abertas: o fluxo entra em `FE3E/FE64/FE8A` pelo redirecionamento de pilha (`$88:C7B6`) ou a ordem do bloco é dirigida por dados (`FE20–FE2F` são bytes de dados, não código). **NÃO VERIFICADO.**

## E-008 — Origem de `$3BAE` / `$3BB0` (estático)
- `$80:86B1/86B4` (`0x0086B1`, metade **baixa**): `INC $3BAE; INC $3BB0`. A cópia da metade **alta** (`0x4086B1`, CPU `$00/$40:86B1`) tem `STZ $3BAE; STZ $3BB0`. **CONFIRMADO** (estático); só essas duas ocorrências existem como `abs` em toda a ROM.
- Alcançabilidade: um percurso estático por fluxo direto (599 instruções, a partir de `$80:83F2` com `M=X=0`) **alcança** `$80:86B1` e `$80:86B4`. Alcançável ≠ executado (pode estar sob condição). **CONFIRMADO** como alcançabilidade estática.
- Outras escritas possíveis (`MVN` de `$80:83FF`, indexadas, indiretas, DMA): **NÃO EXCLUÍDAS**.
- Por que o breakpoint Execute não disparou: **HIPÓTESES**, a testar em `docs/EXPERIMENTOS_3BAE_3BB0.md`.

## Defeitos conhecidos do Studio (não corrigidos)
- `CpuState` perde o estado após `CLC; XCE` (Carry não rastreado): o reset `$00:83D7` (`CLC; XCE; REP #$30`) deixa `M/X` desconhecidos e o disassembly para em `LDA #imm`. Rastrear `C` imediatamente antes de `XCE` resolveria.
- `examples/mesen_dma_capture.lua` lê `emu.getState().cpu.pc`; o formato das chaves de CPU no Mesen 2 **não foi verificado**. Se for plano (`"cpu.pc"`), a coluna PC continua vazia.
- `__pycache__/*.pyc` estão versionados no `main` (commit `aed9f1a`); o `.gitignore` novo os ignora, mas não os removeu do índice.
