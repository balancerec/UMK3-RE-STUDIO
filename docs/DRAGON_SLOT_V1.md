# Slot 0x0A (quadro do Dragão) — estudo estático v1

Ferramentas: `backend/dragon_slot.py`, `tools/dragon_slot_report.py`, testes `tests/test_dragon_slot*.py`.
ROM de referência: Deluxe 2.2, SHA-256 `f512ef86…487bdd`. Endereços: o banco `$86` e o `$C6` são espelhos do mesmo offset de arquivo (`$86:A726` = `0x06A726`).

Rótulos: **CONFIRMADO POR CÓDIGO-FONTE** aqui significa bytes lidos da ROM e decodificados (não há código-fonte do jogo);
**CONFIRMADO POR TRACE** só se aplica ao que o EXP001 mostrou; **CONFIRMADO POR TESTE** = teste automatizado sobre a ROM;
**HIPÓTESE** e **NÃO VERIFICADO** como definidos no projeto. Nenhum comportamento de execução foi confirmado nesta etapa.

## 1. Por que Ermac ↔ Jax pulam o Dragão
- Tabelas direcionais (`$86:A6C6/A6DE`): `up[0x10] = 0x0A` e `down[0x03] = 0x0A`, ou seja, o Dragão fica entre Jax (3) e Ermac (0x10). CONFIRMADO POR CÓDIGO (teste real).
- Rotina `$86:A726`: se o próximo índice é `0x0A` e `$1C57 != 1`, ela troca o índice por 3 (cima), 0x10 (baixo), 9 (esquerda) ou 0x0B (direita) e dobra o passo do cursor no eixo. Esse é o salto. CONFIRMADO POR CÓDIGO.
- Com `$1C57 == 1` o desvio é ignorado e o cursor pode ficar em `0x0A`. Alcançabilidade (BFS sobre as tabelas): com estado 0 só o índice 10 é inalcançável; com estado 1 os 24 são alcançáveis. CONFIRMADO POR TESTE (modelo estático).

## 2. Papel de `$1C57`
Escritas: `$84:A306` (0), `$84:A38E` (0), `$84:A398` (1, após 0x20 quadros), `$84:A3F4` (2). Leitores: `$84:A2A3`, `$84:A2E2`, `$84:A3EC`, `$86:A73F`. CONFIRMADO POR CÓDIGO.
Nomes dos estados (0 repouso, 1 aberto, 2 fechando): HIPÓTESE. O EXP001 viu o cursor em `000A` 4 vezes (CONFIRMADO POR TRACE), compatível com o estado 1 — não prova a causa.

## 3. Hipóteses
| # | Hipótese | A favor | Contra / lacuna | Experimento | Critério |
|---|---|---|---|---|---|
| H1 | Bloqueio explícito em `$86:A767/A777` | blocos de redirecionamento decodificados; Extended Edition neutraliza o `CMP` | — | trace com cursor em Jax/Ermac e estado 0 | PC passa por A75E/A76E e `$3A50` recebe 3/0x10 |
| H2 | `$1C57=1` preserva `000A` | gate `CMP #1` no código; EXP001 | não observado ainda o valor de `$1C57` nas 4 ocorrências no trace correlacionado | gravar `$7E:1C57=1` na seleção e mover Jax↓ | `$3A50 == 0x0A` e o cursor desenha no quadro |
| H3 | Identidades compartilhadas dependentes de estado | `$1C59` muda pelo rodízio; ID da tabela é 0xFF no índice 0x0A | origem de `$3BAE/$3BB0` ainda NÃO VERIFICADA | trace do rodízio com `$1C59`/`$36D0` | ID resolvido muda sem o cursor mudar |
| H4 | Retratos vêm de tabela diferente da de identidades | cadeia `$84:A2B9` só distingue `$1B`; resto → quadro 0 | tabela gráfica de Sheeva/Smoke/"Idels" NÃO localizada | trocar `$1C59` com Mesen e ver o retrato | retrato muda sem mudar a tabela de ID |

Causa dos retratos repetidos de Motaro: `$84:A2B9..A2CF` escolhe o quadro 2 só para `$1C59 == 0x1B`; todos os demais IDs (`0x1A, 0x0B, 0x16, 0x19`) usam o quadro 0. CONFIRMADO POR CÓDIGO. Observação: o ID `0x19` é o Chameleon segundo o TCRF (códigos PAR); corrige a leitura anterior.

## 4. Inventário comunitário (A) e reutilização (B)
Leitura direta pelo agente: repositório público `VrepliroidV/umk3-snes---arcade-edition` (só README, sem código) e o pacote IPS "Extended Edition" fornecido pelo usuário (README/LEIA-ME e comparação byte a byte). NÃO LIDOS (indisponíveis ao agente): a página snesforever de nov/2026 e a página do Deluxe do Lucas Dext5r. Autoria e versão são as declaradas nos READMEs; não foram verificadas de forma independente.
- IPS Extended Edition (evidência diferencial): `CMP #$0A → #$FF` em `0x06A73B`, tabela movida (banco 86→47 em `0x06A72D`), hook em `$86:A7AA`, `BEQ→BRA` em `0x04A32E` (rodízio desligado), grade 7/7/5/5/5. Reutilizável como **método**, não como bytes: não copiamos o patch.
- Dados públicos: Data Crystal rotula `7E3BAE`/`7E3BB0`; TCRF documenta PAR `7E36D019`/`7E52C819` = ID 0x19.

## 5. Mecanismos (C)
1. Desativar o ID especial (`CMP #$FF`): 1 byte; remove o slot por completo; o Dragão deixa de ser selecionável.
2. Forçar `$1C57 = 1` (ou NOP no `BNE` de `0x06A745`): mantém o slot selecionável sempre; o ID resolvido vem de `$1C59` (rodízio).
3. Realocar tabelas + grade nova (Extended Edition): maior liberdade, maior risco (hook, banco novo).

## 6. Plano de implementação (D) — NÃO APLICADO, NÃO VALIDADO
Nenhum IPS foi gerado: a regra do projeto exige validação em emulador antes.
| Nível | Mudança | Reversão | Risco |
|---|---|---|---|
| 0 | `$7E:1C57 = 1` no Memory Viewer (sem patch) | recarregar | nenhum |
| 1 | `0x06A73B`: `0A → FF` (ou NOP no `BNE` em `0x06A745`) | restaurar byte original `0A` | `$1C59` pode ser 0 → ID 0 |
| 2 | `0x04A32E`: `F0 → 80` + byte de tabela em `0x06A211` | restaurar `F0` e o byte | rodízio desligado muda o fluxo de Idels/Smoke/Sheeva |
Pré-condição: conferir SHA-256 da ROM. Checklist: navegar pelos 24 índices nos 4 sentidos; confirmar ID, sprites, sons, animações e luta (aparecer visualmente não basta).

## 7. Experimento Mesen
Na tela de seleção, no Memory Viewer escreva `$7E:1C57 = 01`, mova Jax↓ e Ermac↑ e capture trace com `backend/selection_probe.py`. Sucesso: `$3A50 == 0x0A` e o cursor desenha no quadro. Falha: o cursor continua em 3/0x10 → H2 refutada, rever o gate.

## 8. Limites
Execução real não observada; efeito de `$F5A6/$3A50/$3A52` (ramos neutralizados) desconhecido; `JSL $84:FE2A` não analisado; tabela gráfica dos retratos não localizada.
