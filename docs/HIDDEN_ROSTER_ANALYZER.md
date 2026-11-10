# Hidden Roster Analyzer v2

Analisa traces de CPU 65C816 exportados pelo Mesen e reconstrói, **somente com o que o trace mostra**, a linha do tempo das variáveis do slot oculto. Código: `backend/trace65816.py` (parser), `backend/hidden_roster_analyzer.py` (análise), aba **Hidden Roster Analyzer** da interface.

> **Estado das evidências.** Nenhum trace real foi fornecido durante o desenvolvimento. Os testes e a demonstração usam um trace **sintético** (`examples/hidden_roster_trace_sintetico.txt`, gerado por `tools/make_synthetic_trace.py`): PCs e instruções seguem o código estático da ROM, mas registradores e valores de memória são fictícios. **Nada neste módulo confirma, por si só, a origem de `$3BAE`/`$3BB0`.** Isso depende de um trace real (ver "Próximo experimento").

## Política de evidência
| Rótulo | Significado |
|---|---|
| **CONFIRMADO** | O trace mostra o valor (leitura), ou o valor gravado foi visto numa leitura posterior coincidente |
| **DERIVADO** | Calculado de dados do trace (ex.: `STA` grava `A`; `INC` = anterior + 1). Ainda sem leitura posterior |
| **INFERIDO** | Dedução de segunda ordem (usado no grafo, para arestas estáticas não observadas) |
| **NÃO VERIFICADO** | O trace não traz o dado necessário. Nenhum valor é inventado |

Regras centrais: (1) o valor após `=` é o conteúdo **antes** da instrução; em `STA/STZ/INC/…` ele é o valor **anterior**, nunca o gravado; (2) um endereço só é calculado (`DB`, `D`, `S`, `X`, `Y` do trace) para modos determinísticos e fica marcado `calculado`; indiretos sem `[$bbaaaa]` não geram evento; (3) valores que mudam sem escrita visível viram **desvio** (`memory_mismatches`), nunca são "corrigidos" em silêncio.

## Formato de entrada
Uma instrução por linha. Reconhecido (tokens por nome, em qualquer ordem):
```
86A203 lda $1c59 [$7E1C59] = $001A A:0000 X:0003 Y:0000 S:01F3 D:0C00 DB:7E P:nvmxdIzc
```
- PC de 6 dígitos = 65C816. PC de 4 dígitos, ou etiqueta `[SPC]`/`SPC:`, = **SPC700** (contado, não decodificado, não interfere na continuidade da CPU). A heurística por largura do PC é **INFERIDA**.
- `P`: letras `NVMXDIZC` (maiúscula = ligado) ou hexadecimal de 2 dígitos. Largura 8/16 bits vem de `M`/`X`; sem `P`, vem da largura do valor exibido; sem nenhum dos dois, o valor gravado fica desconhecido.
- Linhas começando com `#` são comentários; linhas ilegíveis são contadas e ignoradas (nunca interrompem a análise). Limite de 128 MiB.

### Configurar o Trace Logger do Mesen 2
A documentação oficial do Trace Logger lista as tags `[PC]`, `[Disassembly]`, `[EffectiveAddress]`, `[MemoryValue]`, `[A]`, `[X]`, `[Y]`, `[SP]`, `[P]`, `[Cycle]`, `[Scanline]`, `[FrameCount]`, `[CycleCount]`, com opções após vírgula (`[PC,6h]`) e um campo *Condition* com a sintaxe dos breakpoints ([mesen.ca/docs/debugging/tracelogger.html](https://www.mesen.ca/docs/debugging/tracelogger.html)). **A documentação não cobre as tags de `D`/`DB` nem como CPU e SPC700 são marcadas no mesmo arquivo.** Portanto:
1. Faça uma captura curta e confira se as linhas trazem `[$7E1C59] = $001A` (endereço efetivo e valor) e `A/X/Y/S/D/DB/P`.
2. Sem `D`/`DB`, o analisador só usa endereços efetivos que o próprio trace mostra (confiança menor nos demais).
3. Use *Condition* para reduzir o volume, pois o buffer do logger é limitado (um trace de 30.000 linhas **não** cobre a execução inteira).

## Saída
`POST /api/hidden-roster/analyze` devolve:
- `meta`: contagens, intervalo de PC, `truncation_notes`.
- `events`: por evento: `seq` (linha), `pc`/`pc_canon`, `instruction`, `access` (`read|write|rmw|block_move`), `address`, `value_before`, `value_after`, `after_basis`, `registers` (como aparecem, antes da execução), `context` (pilha de chamadas e instruções anteriores), `character`, `confidence`, `evidence`, `confirmed_by_seq`.
- `roster`: escritas em `$1C59` com valor, personagem, escritor estático esperado e `consistent_with_static`, e os `$3BAE/$3BB0` lidos antes. `sequence` lista as mudanças **observadas neste trace**.
- `graph`: blocos e arestas `EXECUTADO (trace)`, `EXECUTADO + ESTÁTICO` ou `INFERIDO (estático, não observado)` (esta última só com a ROM carregada).
- `anomalies`, `limitations`.

Endereços monitorados por padrão: `$7E:1C59`, `3BAE`, `3BB0`, `3A50`, `36D0`, `52C8` (16 bits). `pc_canon` colapsa espelhos (`$84:A349` → `$C4:A349`); `$00/$40` (metade alta) **não** colapsam com `$80/$C0` (ver E-002).

Também: `GET /api/hidden-roster/status`, `GET /api/hidden-roster/export.json` e `export.csv` (aceitam `var`, `character`, `access`, `min_confidence`).

## MVN / MVP
Cada linha é tratada como **uma iteração** (1 byte, `Y ← X`). Se a linha seguinte tem `PC+3` e `A` não é `0`/`FFFF`, o log foi colapsado em uma linha e o intervalo é estimado por `A+1` (marcado na evidência). Valores copiados vêm da memória sombra reconstruída; origem desconhecida ⇒ `NÃO VERIFICADO`. **Hipótese não verificada:** o Mesen imprime os bancos de `MVN` na ordem do assembler (origem, destino).

## Detecção de traces incompletos
Linhas ausentes/NMI/IRQ (PC não sequencial após instrução que não é desvio), retorno sem chamada no trace (início no meio de uma rotina), número de linhas redondo (possível limite do buffer), arquivo que não termina em quebra de linha. **Retorno que não volta ao chamador** é registrado como `return_redirects`: é consistente com a manipulação de pilha em `$88:C7B6/C7CC` (E-007), mas **também** ocorre com chamada fora do trace; é HIPÓTESE.

## Demonstração (trace sintético)
`Idels → Shao Kahn → Motaro → Sheeva → Human Smoke → Idels`, com os cinco escritores (`$C4:A349`, `$C4:A36A`, `$FF:FE41`, `$FF:FE67`, `$FF:FE8D`) `consistente com o estático`, `INC $3BAE/$3BB0` derivado e confirmado por leituras posteriores, MVN colapsado propagando zeros (131.070 bytes) e um retorno redirecionado. É uma **ilustração do funcionamento**, não evidência sobre o jogo.

## Limitações conhecidas
- Um trace é uma amostra; ausência de evento não prova que o código nunca executa.
- Escritas por DMA, SPC700 ou indiretas sem endereço efetivo não são vistas (contadas em `indirect_without_effective_address`).
- Sem `P`/valor exibido, `INC/DEC/ASL…` e `STA` não têm largura: valor desconhecido.
- A memória sombra cobre os 128 KiB de WRAM e só reflete o que o trace mostra; `memory_mismatches` sinaliza quando isso falha.
- Os escritores estáticos de `$1C59` vêm de uma varredura por padrão de bytes (E-005), não de decodificação completa.
- Registradores `D`/`DB` dependem do formato do trace (ver acima).

## Próximo experimento (para resolver `$3BAE`/`$3BB0` e o redirecionamento)
1. Configure o Trace Logger (formato acima) com *Condition* restrita aos PCs de interesse e **inicie antes do reset**; em paralelo carregue `examples/mesen_wram_watch.lua` (escritas em `3BAE/3BB0/1C59` com PC).
2. Faça *Reset*, vá à tela de seleção, alterne os ocultos e pare.
3. Importe o trace na aba **Hidden Roster Analyzer** e anote: primeira escrita em `$3BAE/$3BB0` depois do `MVN` de `$80:83FF` (e se vem de `$80:86B1`/`$C0:86B1`); valores lidos em `$C4:A341/A362`; se `$FF:FE3B/FE61/FE87` entram pelo `LDA $3BAE` ou diretamente em `FE3E/FE64/FE8A`; destino real do `RTL` de `$88:C7B6` (`return_redirects`).
4. Compare `roster.writes[].consistent_with_static` e `memory_mismatches`: qualquer divergência é um achado a investigar, não um erro a ocultar.
