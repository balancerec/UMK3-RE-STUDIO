# Comparador de capturas Mesen — Deluxe 2.2 e 2.3

Este módulo é independente dos analisadores do Claude. **Somente leitura:** não modifica a ROM, WRAM nem arquivos de origem.

## Objetivo

Comparar dois snapshots **completos e da mesma memória**. Identificar os deltas de bytes e apresentar valores de referência sem assumir nomes de personagens ou regras de desbloqueio. Os rótulos `2.2` / `2.3` e SHA-256 da ROM são fornecidos pelo operador; **não são comprovados por um snapshot**.

## Captura dirigida — Mesen

1. Inicie a ROM **Deluxe 2.2** confirmando o arquivo aberto. No Debugger, adicione breakpoint **Write** para CPU Memory `7E3A50`. Desabilite o breakpoint **Write** da região ROM `84F8E9`: ele não demonstra execução do `BNE`; na captura, `84F8E5 CMP APUIO2; 84F8E9 BNE` é um loop de comunicação com áudio.
2. Pare em Shao Kahn: exporte `wram`, `vram`, `cgram` e `oam` (se disponíveis), com nomes **`2.2_shao_*`**. Grave também a ROM SHA-256.
3. Dê um único movimento em direção a Ermac; deixe o **Write** em `7E3A50` interromper e registre **PC, A, X, Y, D, DB, P**, nova palavra e instruções antes/depois. Salve nova WRAM estável como **`2.2_ermac_*`**. Repita com Smoke robô e retorno. **Não confundir Ermac e Cyber Smoke, visíveis, com Smoke humano, Sheeva e Motaro, ocultos.**
4. Se o breakpoint não disparar, desabilite-o e teste **Write** em `7E36D0`, depois em `7E1C59`, **um de cada vez**. Não modifique bytes: é um experimento de observação.
5. Replique a sequência na ROM candidata **Deluxe 2.3**. Compare apenas estados equivalentes e rotule cada snapshot.
6. O resultado do breakpoint de escrita deve ser acompanhado de trace com PC de instrução e CPU flags: **diferenças na WRAM não identificam a instrução produtora**.

## CLI

Use arquivo binário ou dump de texto hexadecimal puro (somente bytes `00 FF 1A...`, sem offsets/títulos). Tamanhos exatos: WRAM 131072 bytes, VRAM 65536 bytes, CGRAM 512 bytes, OAM 544 bytes.

```powershell
python -m backend.roster_capture --kind wram `
  --a ".\capturas\2.2_shao.wram" `
  --b ".\capturas\2.2_ermac.wram" `
  --version-a 2.2 --version-b 2.2 `
  --label-a "Shao Kahn" --label-b "Ermac" `
  --output ".\capturas\2.2_shao_para_ermac.json"
```

Comparação entre versões, após capturar snapshots comparáveis:

```powershell
python -m backend.roster_capture --kind vram `
  --a ".\capturas\2.2_shao.vram" `
  --b ".\capturas\2.3_shao.vram" `
  --version-a 2.2 --version-b 2.3 `
  --output ".\capturas\2.2_vs_2.3_vram.json"
```

O JSON inclui hashes dos snapshots, versões **declaradas**, campos candidatos e delta por intervalo/segmento. Na WRAM, os endereços sob observação são `7E:1C59`, `7E:36D0`, `7E:3A50`, `7E:3BAE`, `7E:3BB0`, `7E:52C8`, `7E:52CA`. Esses rótulos **não equivalem a descoberta de flag de desbloqueio**.

O SHA de ROM pode ser registrado opcionalmente com `--rom-sha-a` e `--rom-sha-b`, mas é uma anotação, não validação criptográfica da origem do snapshot.

## Validação

```powershell
python -m pytest -q tests/test_roster_capture.py
python -m pytest -q
```

**Limitações**: screenshots, gravações e dumps em instantes diferentes podem gerar divergências transitórias. OAL/OAM/CGRAM devem ter o formato e tamanho corretos; `OAM=544` é o dump bruto tradicional, não a string formatada do viewer. Um trace SPC700 intercalado com CPU não é evidência automática de alteração de personagem. Nenhum relatório afirma que uma ROM modificada esteja autenticada como 2.3 apenas pelo nome.
