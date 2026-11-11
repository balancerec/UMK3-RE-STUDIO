# Research Pipeline v1 — Arcade Edition Beta 71

## Escopo efetivamente implementado

Ferramenta **somente leitura**, CLI: `python -m backend.research_pipeline <ROM.sfc> --out pesquisa.json`.

1. Autenticação obrigatória: 8.388.608 bytes, MD5 `b04388eef6071792d85f97dab46c471c`, SHA-256 `60b948a785ed86d927b02ce862c0f37dfbed09ba725ab57902dfd34d1c832d6e`.
2. Extração de ID e quatro tabelas de 29 bytes do banco 47; matriz 7/7/5/5/5, destinos e conectividade.
3. Janela de disassembly linear para checkpoints conhecidos, usando o `backend.core.decode_one` existente, status E=0 M=0 X=0 **assumidos**, com advertência explícita sobre fluxo real.
4. Extração de duas tabelas candidatas de 29 palavras cada em `47:B601` e `47:B63B`; sem confundir hipótese semântica com evidência binária.
5. Comparação de snapshots de VRAM, CGRAM e OAM; candidatos a tiles 4bpp e entradas de paleta alteradas.
6. Saída JSON, com recusa de sobrescrever relatório existente. Nenhuma alteração nos recursos da ROM.

## Autenticação verificada independentemente

Aplicação do IPS `UMK3_arcade_edition.ips` ao arquivo original de 4 MiB:

- MD5 original: `0644da71f79d405a22934daa1474cefc`
- 7.161 registros de patch.
- MD5 saída: `b04388eef6071792d85f97dab46c471c`
- SHA-256 saída: `60b948a785ed86d927b02ce862c0f37dfbed09ba725ab57902dfd34d1c832d6e`

Nenhum desses arquivos binários é incorporado ao repositório.

## Mapa binário confirmado na versão autenticada

| CPU | Offset físico | Significado |
| --- | --- | --- |
| `86:A73A` | `06A73A` | `C9 FF 00` = `CMP #$00FF`, em 16 bits |
| `86:A7A8` | `06A7A8` | `92 94 22 4D CF 47` = `STA ($94); JSL $47CF4D` |
| `47:B570` | `47B570` | 29 bytes: IDs |
| `47:B58D` | `47B58D` | 29 bytes: cima |
| `47:B5AA` | `47B5AA` | 29 bytes: baixo |
| `47:B5C7` | `47B5C7` | 29 bytes: esquerda |
| `47:B5E4` | `47B5E4` | 29 bytes: direita |
| `47:B601` | `47B601` | 29 palavras: candidato X |
| `47:B63B` | `47B63B` | 29 palavras: candidato Y |
| `47:CF4D` | `47CF4D` | Rotina adicional pós-movimento |

### Evidência para coordenadas

Primeiras sete palavras em `47:B601`: `0012 0044 0076 00A8 00DA 010C 013E` — incremento constante `0x32` (50).
Em `47:CF4D` há `LDA ($94); ASL A; TAY` seguido de leituras longas em `47:B63B` e `47:B601`, e escritas indexadas em `$3DA8` / `$3F18`.

**Interpretação ainda não confirmada em execução:** tabelas X/Y para cada índice de cursor. O significado de `$2A`, das duas regiões de WRAM e a ordem exata dos eixos devem ser observados no Mesen.

## Comparações gráficas

```powershell
python -m backend.research_pipeline ".\arcade-beta71.sfc" --out ".\research.json" `
  --vram-a ".\before_vram.dmp" --vram-b ".\after_vram.dmp" `
  --cgram-a ".\before_cgram.dmp" --cgram-b ".\after_cgram.dmp"
```

Requer dumps brutos com tamanho exato (VRAM 65536; CGRAM 512; OAM 544 bytes). O relatório não assume que diferenças da VRAM equivalham a dados diretamente contíguos na ROM.

## Critérios para chamar algo de CONFIRMADO POR TRACE

- Rotina `47:CF4D` executada na mudança de slot, com PC e registradores observados.
- Valores efetivamente lidos nas tabelas X/Y, base de `D` e `DB` conhecidos.
- Endereços efetivos e valores antes/depois das escritas em `$3DA8,X` e `$3F18,X`.
- Correlação do slot com retrato, identidade em `$36D0/$52C8` e lutador efetivamente carregado.

## Testes

```powershell
python -m pytest -q tests/test_research_pipeline.py
python -m pytest -q
```

Os testes incluídos são **sintéticos** e não substituem a regressão real em emulador.

## Próximas entregas, não implementadas

- Extrator automático de referências ASM profundas (CFG e dataflow), com propagação de PBR/DBR/D.
- Decodificador confirmado do formato comprimido utilizado pelo jogo.
- Identificação de ponteiros reais de retratos via logs DMA.
- Integração visual na interface Execution Research.
- Editor/reinserção/patch da ROM (não realizados por este módulo).
