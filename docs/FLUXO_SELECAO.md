# Fluxo da seleção de personagens (reconstruído)

Baseado em código lido da ROM (ver `docs/EVIDENCIAS.md`). Setas tracejadas = **NÃO VERIFICADO**.
Endereços CPU em notação `$banco:endereço`; `$7E:` omitido nas variáveis WRAM.

```mermaid
flowchart TD
    PAD["$0A = edge do joypad<br/>0800 cima · 0400 baixo · 0200 esq. · 0100 dir."] --> NAV["$86:A383 navegação<br/>$0E = índice atual (lido de ($94) = $3A50 no P1)"]
    NAV -->|"cima"| TU["tabela $86:A6C6"]
    NAV -->|"baixo"| TD["tabela $86:A6DE"]
    NAV -->|"esq."| TL["tabela $86:A6F6"]
    NAV -->|"dir."| TR["tabela $86:A70E"]
    TU & TD & TL & TR --> RD["$86:A726: A = base da tabela<br/>LDA [$12],Y com Y = $0E → novo índice"]
    RD --> SP{"índice == $0A?<br/>$86:A73A"}
    SP -->|"não"| WR["$86:A7A6: STA ($94) → $3A50 = índice"]
    SP -->|"sim"| HV["$86:A73F… valida $1C57, $F5A6, $3A50, $3A52<br/>(condições NÃO reconstruídas)"]
    HV -.-> WR
    WR --> RES["$86:A164 → JSL $86:A1F6<br/>ID = tabela[$86:A207 + índice]<br/>se ID == FF → ID = $1C59"]
    RES --> S36["$36D0 = ID resolvido"]
    S36 --> SY["$88:94EC → $0A = $36D0 → JSL $88:9809"]
    SY --> S52["$88:980F: $52C8 + X = ID  (X=0 → $52C8 = P1)"]
    HID["rotina dos ocultos $C4:A2FC…<br/>$FF:FE3E… (script/pilha)"] -->|"escreve ID"| C59["$1C59"]
    C59 -.-> RES
    B["$3BAE / $3BB0"] -.-> HID
```

## Pseudocódigo fiel ao observado
```c
// $86:A1F6  (confirmado por bytes)
uint16_t resolve(uint16_t idx){ uint8_t id = rom[0x86A207+idx]; return id==0xFF ? wram16(0x1C59) : id; }

// $86:A383..A3E5 (confirmado por bytes); a parte do índice 0x0A em $86:A73A+ NÃO está reconstruída
uint16_t next_index(uint16_t cur, uint16_t pad){
  if (pad & 0x0800) return up[cur];
  if (pad & 0x0400) return down[cur];
  if (pad & 0x0200) return left[cur];
  if (pad & 0x0100) return right[cur];
  return cur;
}
```
Observação: o fluxo real chama `$86:A661` (com `X` = 0, 7, 14, 21) antes de cada tabela e só segue se o Carry volta setado (`BCC` pula a direção). A função de `$86:A661` ainda não foi analisada.

## Pontos de entrada da alternância dos ocultos (estáticos)
| Entrada | Observação |
|---|---|
| `$C4:A2FC` | zera `$1C57` e `$1C59` e prepara `$EB5C` |
| `$C4:A328` | sai se `$3BAE`=`$3BB0`=0; senão espera `$36C6` e decide Shao Kahn (`$3BAE`) ou Motaro (`$3BB0`) |
| `$FF:FE3E`, `FE64`, `FE8A` | escrevem Sheeva, Human Smoke e Idels; chegam por fluxo ainda não resolvido |
| `$88:C7B6` | chamado em todos os blocos (`PEA $84A3 / PEA $8D00 / PHA / JSL $88C7B6`); candidato ao redirecionamento de retorno por pilha |
