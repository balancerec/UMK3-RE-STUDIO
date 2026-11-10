# UMK3-RE-STUDIO — Plano de Evolução v2.0
**Status:** Planejado, sujeito a validação experimental
**Última revisão:** 2026-11-10
**Referência técnica:** [MesenCE](https://github.com/nesdev-org/MesenCE), fork do Mesen 2
**Princípio:** estudar a arquitetura de ferramentas existentes, implementar soluções próprias e documentar evidências reproduzíveis; evitar importar código de terceiros sem revisão de dependências e licenças.

## 1. Missão
Evoluir o UMK3-RE-STUDIO de analisador de ROM/dumps para uma plataforma integrada de pesquisa em engenharia reversa de Ultimate Mortal Kombat 3 Deluxe 2.2 (SNES), sem dependência de contagem manual de instruções.

### Objetivos mensuráveis
- Gravar automaticamente eventos de CPU/WRAM relevantes, com ordem e contexto completos.
- Comparar transições entre índices de seleção, incluindo slot secreto.
- Ingerir evidências antigas e novas usando nomenclatura padronizada.
- Preservar valores anteriores e posteriores *somente quando observáveis*, classificando evidência.
- Reconstruir dependências e caminhos divergentes sem confundir gráficos com identidade lógica.
- Suportar experimentos reproduzíveis com hash da ROM, versão de emulador e protocolo de captura.

### Não objetivos da primeira etapa
- Criar um novo emulador de SNES.
- Editar ROMs automaticamente ou distribuir ROMs comerciais.
- Incorporar código-fonte GPL do MesenCE ao Studio.
- Controlar remotamente o emulador via rede antes de validar automação local e suas APIs.
- Prometer acesso em tempo real à memória com latência ou consistência não testadas.

## 2. Referências e fronteiras
MesenCE contém `Core/Debugger/LuaApi.cpp`, `Core/Debugger/BreakpointManager.cpp`, `Core/Debugger/MemoryDumper.cpp`, `Core/SNES/Debugger/TraceLogger/SnesCpuTraceLogger.cpp` e `InteropDLL/DebugApiWrapper.cpp`. Estudar suas interfaces e semântica antes de implementar.
Verificar a disponibilidade e semântica exatas dos callbacks Lua na versão do executável usada pelo pesquisador. O contrato abaixo pertence ao Studio, não pressupõe que todas as operações de captura ou escrita em arquivo estejam expostas nativamente.

## 3. Arquitetura
```text
Mesen 2 / MesenCE
  └─ Lua Capture Agent [captura de eventos, registradores, amostras]
       └─ files JSONL + metadata.json + optional binary dumps
            └─ Local Capture Importer [validação, hashes, normalização, idempotência]
                 ├─ Capture Manager
                 ├─ Memory Research Lab
                 ├─ Execution Flow Analyzer
                 ├─ Hidden Roster Analyzer
                 └─ Graphics Research Lab
```
O agente pode rodar sem o Studio aberto; o Studio pode analisar capturas sem o Mesen aberto. Preferir *file-based bridge* inicialmente. Nunca permitir que dados coletados sejam executados como código.

## 4. Contrato de evento proposto (JSONL v0.1)
Cada linha é um JSON independente; entradas incompletas são rejeitadas ou sinalizadas, jamais interpoladas.

```json
{
  "schema_version":"0.1",
  "session_id":"exp001_run01",
  "seq":42,
  "kind":"memory_write",
  "cpu":"snes",
  "pc":"86A385",
  "memory_type":"WRAM",
  "address":"0C0E",
  "width_bits":16,
  "value_before":10,
  "value_after":11,
  "value_after_status":"confirmed",
  "registers":{"a":"000B","x":"0015","y":"0002","d":"0C00","db":"7E","p":"nvmxdizC"},
  "frame":null,
  "cycle":null,
  "timestamp_utc":null
}
```
**Exemplo de formato, não captura real.** `value_after_status` aceita `confirmed`, `derived`, `unknown`; se o agente não tiver leitura confiável após a execução, `value_after=null` e `unknown`. `width_bits` deve refletir M/X efetivos, não ser presumido. `seq` é crescente na sessão e `session_id` isola execuções. Endereços de CPU e WRAM são espaços distintos. Evitar confundir o PC do callback com o PC de uma instrução pré/pós-execução: documentar a fase do callback.

### Manifesto da sessão
Referenciar `docs/PADRAO_NOMENCLATURA_CAPTURAS.md`, registrar SHA-256 da ROM, versão completa do emulador, perfil de coleta, endianness/region sizes, hashes e tamanhos dos artefatos, momento de início/fim, estado visual, índice lógico, ID resolvido e anotações. Todas as ausências são `null`.

## 5. Módulos

### 5.1 Mesen Bridge v0.1
- Perfil `hidden_roster`: observar `7E:0C0E`, `7E:3A50`, `7E:1C59`, `7E:36D0`, `7E:52C8`; PCs `86:A385`, `86:A733`, `86:A738`, `86:A73A`, `86:A7A8` (precisam confirmar execução na ROM exata).
- Registrar execuções, leituras/escritas, valores e contexto quando a API oferecer.
- Contador de instruções: reportar somente se houver contador confiável; `step_estimate` separado.
- Exportar JSONL com rotação e limite configurável; tratamento de erro ao gravar, sem interromper o emulador desnecessariamente.
- Implementação própria; scripts versionados e sem qualquer download implícito de ROM.
- **Validação inicial:** reproduzir um evento conhecido de atualização de cursor com arquivo pequeno, reabrível e sem registros duplicados.

### 5.2 Capture Manager
- Evoluir aba existente de gerador de nomes para sessões e importação por manifestos.
- Validação de tamanho, digest, esquema, tipos, timestamps, nomes e conteúdo JSONL.
- Reimportação idempotente e armazenamento local isolado por experimento.
- UX: árvore de experimentos, linha do tempo, estado de captura e exportação de pacote.

### 5.3 Memory Research Lab
- Diff de snapshots WRAM, VRAM, OAM, CGRAM com dimensão e endereço-base explícitos.
- Leituras de bytes, words little-endian, máscara de bits; filtros por região e mudança.
- Atribuir origem de uma mudança somente com trace ou evento validado.

### 5.4 Execution Flow Analyzer
- Rastreamento de `STA`/`LDA`, chamadas/retornos, instruções condicionais e contexto de flags.
- Localizar primeira divergência entre duas execuções com alinhamento robusto contra loops.
- Mostrar cadeia `fonte → operação → destino`, com incerteza representada explicitamente.

### 5.5 Hidden Roster Research v4
- Mapear `slot index`, `character ID`, estado visual e possível alternativa de navegação.
- Investigar ROM tables (ex. rotinas próximas a `86:A731` e `86:A73A`) mediante testes controlados.
- Não nomear flags como 'unlock' até existir contraprova com estado bloqueado/desbloqueado.

### 5.6 Graphics Research Lab
- Decodificação e comparação de tiles SNES e paletas de CGRAM.
- Tratamento de OAM e overlays de sprites; dependência explícita do modo gráfico.
- Exportação de imagens e proveniência do dump original.

### 5.7 Research Notebook
- Hipóteses + experimento + evidência + conclusão + grau de confiança.
- Citações de `session_id`, `seq`, hash, offsets e ROM SHA.
- Estados: confirmado, derivado, inferido, não verificado, refutado.

## 6. Fases e critérios de aceite
| Fase | Entrega | Critério objetivo |
|---|---|---|
| 0 | Auditoria de compatibilidade MesenCE/Mesen 2 | Versão Lua e callback verificados no binário usado; teste de evento mínimo |
| 1 | Mesen Bridge v0.1 | Transição de cursor produz JSONL legível e valores condizentes com o trace bruto |
| 2 | Capture Manager v1 | Importação + SHA-256 + reimportação idempotente + manifesto válido |
| 3 | Memory Research Lab | Diff WRAM entre dois snapshots com testes de endianness e tamanho |
| 4 | Execution Flow | Cadeia de origem do índice e primeira divergência visíveis em casos de teste |
| 5 | Hidden Roster v4 | Dois caminhos de navegação reprodutíveis + identidade lógica verificada |
| 6 | Graphics Lab | Tile/paleta/sprite renderizados com parâmetros documentados |

## 7. Estratégia técnica
- Preservar backend Python e frontend HTML/JS atuais.
- Não exigir alteração da ROM. Trabalhar com arquivos fornecidos pelo pesquisador.
- Começar com exportação local e importação manual; evitar DLL/interop até demonstração de necessidade.
- Se for inevitável um helper nativo: processo isolado, protocolo versionado, verificação de ABI, sem injeção não validada.
- Proteger o backend de arquivos malformados/huge dumps: limites de tamanho, parsing incremental, validação estrita.
- Não usar `eval` com dados vindos de traces.
- Rotacionar arquivos para minimizar impacto no desempenho do Mesen; medir overhead.

## 8. Testes
1. Unit tests de validação de evento, endereços e timestamps ausentes.
2. Replay determinístico dos traces já capturados; confirmar `0C0E` e `3A50` sem extrapolação.
3. Teste integrado de evento no Mesen com ROM autorizada do pesquisador.
4. Comparação A/B com mesmo hash da ROM, input documentado, breakpoints e save state.
5. Teste de corrupção/truncamento e limite de arquivos.
6. Windows como alvo primário; CI com Ubuntu e Windows para o parser e backend.

## 9. Primeiro sprint (executável)
- [ ] Confirmar compatibilidade e callbacks do Mesen utilizado; anotar versão e ROM SHA.
- [ ] Implementar `tools/mesen_bridge/README.md` e perfil versionado `hidden_roster.json`.
- [ ] Criar script Lua mínimo de callback para WRAM `0C0E` e `3A50`, com logging controlado.
- [ ] Criar parser Python de JSONL com schema, sequenciamento e validações.
- [ ] Criar testes automatizados com fixtures sintéticas e trace conhecido.
- [ ] Integrar visualização de eventos no Capture Manager, apenas leitura.
- [ ] Documentar métricas de overhead e limitações.

## 10. Decisões pendentes
- Qual release/build do Mesen 2/MesenCE usada nos experimentos?
- API Lua exata para callbacks por execução e leitura de estados nesse build.
- Viabilidade de escrita incremental JSONL pela sandbox de scripts Lua desse build.
- Tamanho padrão de buffers e política de retenção.
- Se e quando adotar interop nativo.

**Regra central:** cada afirmação sobre comportamento da ROM deve estar vinculada a uma evidência com fonte, endereço e sessão. Referência ao MesenCE serve para entendimento arquitetural, não para cópia indiscriminada de código.
