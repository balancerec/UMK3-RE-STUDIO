# Decision Trace Diff v3 (primeira entrega)

Comparador **somente leitura** de duas capturas reais do Trace Logger do Mesen 2, integrado à aba **Hidden Roster Analyzer**.

## Pergunta experimental

Por que, partindo de Jax, o cursor é enviado para Ermac (índice `0010`) enquanto outra tentativa permite acessar o slot especial (índice `000A`)?

O ponto de observação é a gravação executada em `86:A7A8 STA ($94)`, com endereço efetivo `[$7E3A50]`. O código faz uma análise **comparativa**, não prova automaticamente o motivo do bloqueio.

## Uso

1. Com o debugger do Mesen, configure **CPU Execute** em `86:A7A6` e WRAM Write em `$7E:3A50`. No Trace Logger, registre **registradores A/X/Y/S/D/DB/P**, endereço efetivo e valor anterior, com a captura começando **antes** da decisão.
2. Capture A: tente descer de Jax para o slot quando ele mostrar o dragão e registre o caminho que resulta em Ermac.
3. Capture B: tente entrar no slot quando ele estiver acessível, registrando o caminho que produz índice `000A`.
4. Abra o UMK3 RE Studio, acesse **Hidden Roster Analyzer** e, no painel **Decision Trace Diff v3**, selecione os dois arquivos .txt/.log.
5. Escolha a ocorrência da gravação que deseja comparar (o primeiro `STA` é ocorrência 1) e o comprimento da janela (padrão 160 instruções de CPU). Clique **Comparar decisões**.
6. Examine as diferenças de fluxo, registradores e valores de memória; exporte JSON para manter evidência reproduzível.

## API

`POST /api/hidden-roster/decision-diff` aceita formulário multipart com `trace_a` e `trace_b`, além dos parâmetros `ordinal_a`, `ordinal_b`, `lookback` (1–1000). Cada arquivo é limitado a 128 MiB. Responde com:

- `meta`: quantidades de linhas CPU/SPC700;
- `a`, `b`: instrução de escrita, conteúdo anterior e valor derivado de A/P, caso disponíveis;
- `differences`: trechos exclusivos de fluxo, leituras diferentes e alterações de registradores;
- `branch_differences`: desvios no mesmo PC cujo resultado observado difere;
- `summary`: destino, quantidades e primeira divergência observada;
- `limitations`: regras de evidência.

A ocorrência só é considerada endereço efetivo confirmado se `[$7E3A50]` (ou espelho válido) estiver presente no trace. Um PC estático conhecido sem endereço efetivo é rotulado **NÃO VERIFICADO**.

## Limites

- O valor após `=` no Mesen é a **memória anterior** à instrução.
- O valor escrito é **DERIVADO** dos registradores quando A e largura M estão presentes, não confirmado por leitura posterior.
- O primeiro desvio encontrado pode ser uma consequência, não a origem causal.
- Interrupções, entradas cortadas, gráficos de VRAM e estados de sprite não são reconstruídos nesta entrega.
- Testes em `tests/test_decision_trace_diff.py` são **sintéticos**; nunca representam observações da ROM Deluxe 2.2.
- Não altera ROMs, arquivos de usuário nem a configuração do emulador.

## Próxima etapa

Usar os traces reais do experimento Jax→Ermac versus Ermac→slot e testar breakpoints nos **desvios anteriores** a `86:A7A8`. Só depois documentar uma condição de liberação como confirmada.
