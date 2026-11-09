# Experimentos: origem de `$7E:3BAE` e `$7E:3BB0`

Objetivo: descobrir **quem escreve primeiro** esses campos depois da limpeza geral de WRAM (`$80:83F2–840F`, `MVN`).
Premissa estática (E-008): `INC $3BAE; INC $3BB0` em `$80:86B1/86B4` é alcançável a partir do boot; não foi provado que execute.

## Hipóteses para o breakpoint em `$80:86B1` não ter disparado
| # | Hipótese | Como separar |
|---|---|---|
| H1 | O breakpoint foi criado **depois** do boot (a rotina roda uma vez, logo após o reset) | Criar antes e usar *Reset*/*Power Cycle*; ou usar o script abaixo, carregado antes do reset |
| H2 | A execução ocorre por um **espelho** (`$C0:86B1`); breakpoint de endereço CPU só casa o endereço exato | Pôr o breakpoint no tipo de memória da **PRG ROM**, offset `0x0086B1`, ou em `$C0:86B1`. Confirme no diálogo de breakpoint do Mesen 2 qual tipo de memória é oferecido |
| H3 | O código é alcançável mas está sob uma condição que não ocorreu | Breakpoint em `$80:86A9` (`BPL`) e em instruções anteriores da rotina, para ver o fluxo |
| H4 | O valor `0x0001` vem de outra escrita (indireta, `MVN`, código de outra metade) | Observar a **primeira escrita** após a limpeza (script abaixo registra todas) |

## Procedimento A — script (`examples/mesen_wram_watch.lua`)
1. Carregue a ROM no Mesen 2, abra *Debug → Script Window*, carregue o script e **execute antes do reset**.
2. Faça *Reset*. Deixe o jogo chegar à tela de seleção e então pause.
3. Copie o log. Cada linha: `UMK3_WATCH,<n>,<frame>,<PC>,$7E<endereço>,<valor>`. O PC é "contexto", não prova de atribuição.
4. A primeira linha por endereço **posterior à limpeza** (`PC` fora de `$80:83FF/840F`) é a candidata a origem.
5. Registre: PC, bytes da instrução em PC (`$80:86B1` seria `EE AE 3B`), `$3BAE/$3BB0` antes/depois e estado da tela.

## Procedimento B — breakpoints (sem script)
1. *Write* em `$7E:3BAE` e `$7E:3BB0`, **antes** do reset. Anote cada parada: PC, instrução, valor em `A`.
2. Ignore paradas com PC em `$80:83FF` e `$80:840F` (são `MVN`, E-008/§8.1 do prompt); continue até a primeira que não seja `MVN`.
3. Em paralelo, *Execute* em `$80:86B1` **e** `$C0:86B1`.

## O que concluir de cada resultado
- Primeira escrita pós-limpeza em `$80:86B1`/`86B4` com valor 1 → H1/H2 resolvidas; a cadeia de chamadas dá o contexto do boot. **CONFIRMADO** após o log.
- Escrita por outro PC → investigar esse PC; `INC` em `$80:86B1` seria código morto ou só alcançável sob condição.
- Nenhuma escrita além da limpeza e valores permanecem 0 na seleção normal → as condições vêm de um estado de jogo (por exemplo progresso/código), não do boot. **HIPÓTESE.**

## Experimentos complementares
- **`$1C59`:** *Write* em `$7E:1C59` antes de entrar na seleção; confirmar quais dos PCs de E-005 disparam em cada personagem oculto.
- **`$FF:FE3E/FE64/FE8A`:** *Execute* nesses endereços e em `$FF:FE3B/FE61/FE87`; ver se o fluxo entra pelo `LDA $3BAE` ou pelo `LDA #imm`, e o valor de `$88:C7B6`/`$3A` na entrada (E-007).
- **`$86:A661`:** *Execute* com `X` = 0, 7, 14, 21 e registre o Carry de retorno por direção.
