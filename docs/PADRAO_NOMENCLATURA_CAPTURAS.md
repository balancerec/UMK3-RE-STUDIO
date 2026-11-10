# Padrão de nomenclatura de evidências — UMK3 RE Studio

**Versão:** 1.0 · **Status:** Proposto para adoção no projeto · **Idioma:** pt-BR

## 1. Objetivo

Garantir que dumps binários, traces, save states, capturas de tela e metadados produzidos no Mesen 2 sejam identificáveis, agrupáveis por experimento e comparáveis sem depender do contexto de uma conversa. A nomenclatura descreve a **captura observada**, não uma hipótese sobre como o jogo funciona.

## 2. Convenção principal

```text
umk3dx_<versao>_exp<NNN>_<etapa>[_pc<HHHHHH>]_<estado>_<tipo>.<ext>
```

Exemplo:

```text
umk3dx_v2.2_exp001_dbp01_pc86a385_shaokahn_wram.dmp
```

- `umk3dx`: identificação da família de ROM (Ultimate Mortal Kombat 3 Deluxe).
- `v2.2`: versão da ROM. **Não misture versões** sem uma comparação explícita.
- `exp001`: identificador estável do experimento, com pelo menos três algarismos.
- `etapa`: tipo de captura e ordem temporal.
- `pc86a385` (opcional): endereço **CPU PC no instante exato** da captura, não apenas um breakpoint habilitado.
- `estado`: nome da tela/personagem observado, minúsculo, sem espaços/acentos; ex.: `ermac`, `shaokahn`, `subzero`, `slotoculto`. Em caso de dúvida use `desconhecido`.
- `tipo`: região de memória ou categoria de artefato.
- `ext`: extensão de acordo com os bytes reais exportados.

### Regras de validação

1. Usar somente caracteres ASCII minúsculos `a-z`, números, ponto e sublinhado; endereços hexadecimais sem `$`/`:`.
2. Não introduzir data no nome-base por padrão: registrar o instante em `meta.json`. Para capturas repetidas na mesma etapa, incrementá-la (`dbp02`, `dmid02`) em vez de sobrescrever.
3. Os estados `di` e `df` são relativos à **mesma execução experimental**, não à sessão inteira do emulador.
4. Não declarar uma contagem exata sem confirmação do contador de instruções. Usar `dmid01` + `steps_estimated` quando a contagem for aproximada.
5. O personagem indicado no nome deve descrever o **estado visível**, não necessariamente o ID interno resolvido pelo jogo; registrar os dois separadamente no manifesto.
6. `pc` identifica uma instrução e não informa por si só o tipo do breakpoint: armazenar `memory_type`, `access`, `address` e `pc_at_capture` no manifesto.
7. Manter o arquivo original (e hash) quando for necessário renomear, para preservar a cadeia de custódia dos dados.

## 3. Etapas

| Sigla | Significado | Uso |
|---|---|---|
| `di` | Dump Inicial | Snapshot antes da ação investigada |
| `df` | Dump Final | Snapshot após concluir a ação |
| `dbp01`, `dbp02` | Dump Breakpoint 01/02 | Parada sequencial do debugger |
| `dmid01`, `dmid02` | Dump Intermediário | Snapshot sem número exato de passos |
| `dstep096` | Dump Step 096 | Após **exatamente** 96 instruções verificadas |
| `trc` | Trace | Registro textual de instruções |
| `ss` | Screenshot | Imagem da tela/debugger |
| `meta` | Metadados | Manifesto JSON do experimento |

`dbp01` indica a primeira parada e pode corresponder a breakpoints distintos em execuções distintas. O endereço opcional `pc...` resolve essa ambiguidade quando conhecido.

## 4. Tipos de dados e extensões

| Tipo | Descrição | Extensão padrão |
|---|---|---|
| `wram` | Work RAM (128 KiB) | `.dmp` |
| `vram` | Video RAM | `.dmp` |
| `oam` | Object Attribute Memory, sprites | `.dmp` |
| `cgram` | Memória de paletas | `.dmp` |
| `cpumem` | Visão endereçada pela CPU (mapeamento próprio) | `.dmp` |
| `spcram` | Memória do coprocessador de áudio | `.dmp` |
| `trace` | Trace logger do Mesen (CPU + possível SPC700) | `.txt` |
| `state` | Save state (formato nativo, variável) | manter a extensão original |
| `screenshot` | Captura de tela | `.png` |
| `meta` | Manifesto do experimento | `.json` |

**Não confundir:** dump de VRAM com snapshot da interface visível; OAM/CGRAM não determinam sozinhos a identidade visual. `cpumem` e `wram` não são intercambiáveis.

## 5. Layout por experimento

```text
EVIDENCIAS/
└── EXP001_ermac_slot_subzero/
    ├── dumps/
    │   ├── umk3dx_v2.2_exp001_di_ermac_wram.dmp
    │   ├── umk3dx_v2.2_exp001_di_ermac_vram.dmp
    │   ├── umk3dx_v2.2_exp001_dmid01_shaokahn_wram.dmp
    │   ├── umk3dx_v2.2_exp001_dbp01_pc86a385_shaokahn_wram.dmp
    │   ├── umk3dx_v2.2_exp001_df_subzero_wram.dmp
    │   └── umk3dx_v2.2_exp001_df_subzero_cgram.dmp
    ├── traces/
    │   ├── umk3dx_v2.2_exp001_trc_ermac_slot_trace.txt
    │   └── umk3dx_v2.2_exp001_trc_slot_subzero_trace.txt
    ├── screenshots/
    │   └── umk3dx_v2.2_exp001_dbp01_pc86a385_shaokahn_screenshot.png
    └── metadata/
        └── umk3dx_v2.2_exp001_meta_desconhecido_meta.json
```

A convenção principal é uniforme; o manifesto pode ser encurtado na pasta `metadata/` para `meta.json` caso o projeto prefira. Evite converter contagens aproximadas (96 ou 114–116) em `dstepNNN` preciso.

## 6. Manifesto de evidência (`meta.json`)

```json
{
  "schema_version": "1.0",
  "experiment_id": "EXP001",
  "rom": {
    "family": "umk3dx",
    "version": "v2.2",
    "sha256": null
  },
  "emulator": {"name": "Mesen 2", "version": null},
  "experiment": {
    "description": "Ermac -> slot oculto -> Sub-Zero",
    "start_visual": "ermac",
    "end_visual": "subzero"
  },
  "capture": {
    "stage": "dbp01",
    "visual_state": "shaokahn",
    "resolved_character_id": null,
    "pc_at_capture": "86A385",
    "breakpoint": {"memory_type": "CPU", "access": "Execute", "address": "86A385"},
    "steps_exact": null,
    "steps_estimated": null,
    "time_utc": null
  },
  "artifacts": [
    {
      "filename": "umk3dx_v2.2_exp001_dbp01_pc86a385_shaokahn_wram.dmp",
      "type": "wram",
      "sha256": null,
      "size_bytes": null
    }
  ],
  "notes": "O PC é a localização efetiva da parada, não um endereço apenas monitorado."
}
```

Campos `null` significam informação **não verificada**, nunca valor zero.

## 7. Fluxo de trabalho

1. Criar uma pasta `EXPnnn_<origem>_<destino>` para cada experimento controlado.
2. Registrar ROM SHA-256 e versão do Mesen antes da coleta.
3. Fazer `di` com WRAM e, se necessário, VRAM/OAM/CGRAM.
4. Capturar os breakpoints com PC efetivo, registradores A/X/Y/S/D/DB/P e tipo de acesso.
5. Usar `dmidNN` para passos estimados e `dstepNNN` somente com contagem exata.
6. Fazer `df` e salvar os traces inteiros, sem edição; criar recortes derivados com referência ao arquivo original.
7. Gerar e armazenar o manifesto; comparar dumps compatíveis (mesma ROM, mesma região e critérios).
8. Registrar conclusões como **CONFIRMADO**, **DERIVADO**, **INFERIDO** ou **NÃO VERIFICADO**.

## 8. Gerador integrado ao Studio

Na aba **Gerador de Nomes**, preencher versão, experimento, etapa, PC (quando conhecido), estado visual e tipo. O Studio monta o nome conforme esta especificação; permite copiar, baixar um manifesto JSON e consultar exemplos. O gerador **não importa** dumps, **não infere** personagens e **não modifica** a ROM. Metadados não informados permanecem `null`.

## 9. Rastreabilidade e proteção

- Manter evidências originais; usar hashes SHA-256 para demonstrar identidade de conteúdo.
- Nunca alterar dump para corresponder à hipótese.
- Quando o conteúdo é derivado (recorte/transformação), conservar a referência ao original e intervalo de linhas.
- Não fazer commit de ROMs comerciais/copyright nem dumps que incluam o conteúdo integral de ROM sem revisão; privilegiar documentação e amostras mínimas necessárias.
