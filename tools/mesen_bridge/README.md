# Mesen Bridge v0.1 — prova de conceito

## Status
**Protótipo não validado em execução real.** Baseado na API Lua observada em [nesdev-org/MesenCE](https://github.com/nesdev-org/MesenCE). Não altera a ROM. O Studio ainda não controla o emulador automaticamente.

## Como executar
1. Use o MesenCE com **a mesma ROM** que será analisada; registre a versão e SHA-256 antes do experimento.
2. Abra a ferramenta de Script no Debugger e carregue `capture.lua`.
3. No script, configure o `SESSION_ID`. Por padrão, `OUTPUT_PATH=""` envia linhas para o Script Window via `emu.log`; observe que o histórico visível é limitado.
4. Para salvar em arquivo, habilite **Script Window → Settings → Restrictions → Allow access to I/O and OS functions** e configure `OUTPUT_PATH` para um diretório existente e gravável. Não é necessário habilitar rede.
5. Inicie o script antes de movimentar o cursor, execute o experimento e encerre a captura. Reimporte o JSONL para análise offline quando o importador estiver disponível.
6. Limite: `MAX_EVENTS=20000`. Contagem se refere **a eventos observados**, não ao número total de instruções executadas.

## Monitores pré-configurados
- CPU Execute: `86A353`, `86A355`, `86A385`, `86A733`, `86A738`, `86A73A`, `86A7A8`.
- WRAM Write: `0C0E`, `3A50`, `36D0`, `52C8`, `1C59`.

**Atenção:** endereços CPU são 24 bits em `emu.memType.snesMemory`; endereços WRAM são offsets em `emu.memType.snesWorkRam`, não endereços de barramento `7E...`. A compatibilidade do callback WRAM com seu build específico deve ser testada.

## Semântica de evidência
- `callback_value` é o valor fornecido pela API no momento do callback; **não** é assumido como escrita concluída.
- `value_before` e `value_after` são `null`, e `value_after_status=unknown` até confirmar semântica e ordem dos callbacks em um teste controlado.
- `registers` é a tabela escalar devolvida por `emu.getCpuState()`; o campo exato correspondente ao PC deve ser confirmado pela versão do emulador.
- `seq` conta eventos observados. O agente não realiza passos de CPU, não captura todas as instruções e não deduz a origem de uma escrita sem correspondência temporal verificada.

## Próximos passos
- Validar callbacks no MesenCE usado pelo pesquisador.
- Configurar monitores a partir do formulário do Studio, sem editar Lua manualmente.
- Criar importador JSONL e correlacionar eventos com snapshots.
- Introduzir instrumentação de condições de branches e grafo de fluxo.
- Adicionar controles Start/Stop/Step somente após verificar a API e a interface com o processo nativo.

Código deste projeto é independente, elaborado com base na documentação e semântica das interfaces públicas do emulador.