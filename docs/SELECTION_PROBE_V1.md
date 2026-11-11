# Selection Probe v1 — Slot do Dragão

**Instrumento de diagnóstico somente leitura; nenhum patch da ROM foi validado.**

## Evidências e limites

- **CONFIRMADO POR TRACE RELATADO EM EXP001:** `86:A73A` compara `000A`; os caminhos `86:A767/A76A` e `86:A777/A77A` redirecionam o índice temporário para `0003` e `0010`.
- **CONFIRMADO POR LEITURA ESTÁTICA NO REPOSITÓRIO:** `docs/EVIDENCIAS.md` registra tabela de 24 entradas em `86:A207`, com `0A → FF`, e resolução alternativa por `$1C59`.
- **HIPÓTESE:** `$1C57=0001` modifica a navegação do slot; não há prova de flag de desbloqueio.
- **NÃO VERIFICADO:** qual tabela escolhe o retrato de Motaro, estabilidade dos slots após confirmação ou equivalência binária com Arcade Edition.

## CLI no diretório do projeto

```powershell
python -m backend.selection_probe ".\captures\ermac-jax.txt" --out ".\captures\ermac-jax-selection.json"
python -m pytest -q tests/test_selection_probe.py
```

O módulo reutiliza `backend.trace65816.parse_line`. Lê as instruções e observa os checkpoints `86:A73A`, `86:A73F`, `86:A767`, `86:A76A`, `86:A777`, `86:A77A`, `86:A7A8`, além dos acessos efetivos à WRAM em `$0C0E`, `$1C57`, `$3A50`, `$36D0`, `$52C8` e `$1C59`.

O campo `cursor_destinations_derived` é um **candidato derivado do registrador A**, não leitura posterior. O programa não escreve na ROM ou altera dados da aplicação.

## Próximos experimentos controlados

1. Capturar Ermac → Jax e Jax → Ermac com pelo menos 100–200 instruções antes de `86:A73A` e registradores completos.
2. Registrar `$12`, `$0E`, `$1C57`, `$1C59`, `$3A50`, `$36D0`, `$52C8`; confirmar por readback cada escrita relevante.
3. Comparar as duas decisões no módulo existente Decision Trace Diff v3.
4. Testar temporariamente `$1C57=0001` apenas na WRAM do emulador, depois registrar se o jogo sobrescreve esse valor.
5. Rastrear separadamente a tabela do retrato, confirmação de lutador e comportamento do P2.
6. Antes de propor patch: verificar seleção, luta, sons, animações, vitória, reinício e acesso a todos os demais slots.

## Coexistência

Este módulo é independente da API e da interface atual. A integração na aba Execution Research depende de validação dos dados reais e deve acontecer em PR separado para não interferir em alterações concorrentes.

## Referências públicas

- Lucas Dext5r, UMK3 Deluxe 2.2: https://www.snesforever.com.br/2020/03/ultimate-mortal-kombat-3-project.html
- VrepliroidV, UMK3 Arcade Edition, publicado em 08/11/2026: https://www.snesforever.com.br/2026/11/ultimate-mortal-kombat-3-arcade-edition.html
- Data Crystal, seleção e retratos na versão Genesis (metodologia, **não offsets SNES**): https://datacrystal.tcrf.net/wiki/Ultimate_Mortal_Kombat_3_%28Genesis%29/Tutorials
