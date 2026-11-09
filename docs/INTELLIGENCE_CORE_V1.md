# UMK3 Intelligence Core — Fase 1

Implementação isolada para análise automática inicial de ROMs SNES e consulta
de evidências via API local. **Não modifica** `backend/server.py`, a interface
principal ou os módulos do Hidden Roster Analyzer v2 em desenvolvimento.

## Executar (PowerShell na raiz do projeto)

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.intelligence_api:app --host 127.0.0.1 --port 3091
```

Abra `http://127.0.0.1:3091/docs` para usar a documentação interativa.

1. Envie uma ROM no `POST /api/intelligence/import`.
2. Guarde o `id` retornado.
3. Consulte `GET /api/intelligence/jobs/{id}` até `completed`.
4. Acesse resumo, identidade, bancos, pontos de entrada, xrefs e evidências.

O import inicia automaticamente quatro etapas: `identity`, `banks`,
`entrypoints` e `control_flow`. A análise de controle é limitada a
3.000 instruções e 10.000 referências, para impedir trabalho descontrolado.

## Contrato HTTP v1

| Método | Caminho | Resultado |
| --- | --- | --- |
| POST | `/api/intelligence/import` | Job 202 e progresso |
| GET | `/api/intelligence/jobs/{id}` | Status e etapas |
| GET | `/api/intelligence/jobs/{id}/summary` | Métricas e fontes pendentes |
| GET | `/api/intelligence/jobs/{id}/identity` | Hash, mapping e cabeçalho |
| GET | `/api/intelligence/jobs/{id}/banks` | Bancos paginados |
| GET | `/api/intelligence/jobs/{id}/entrypoints` | Vetores candidatos |
| GET | `/api/intelligence/jobs/{id}/xrefs` | Referências paginadas |
| GET | `/api/intelligence/jobs/{id}/evidence` | Evidências paginadas |
| GET | `/api/intelligence/health` | Saúde da API |

## Evidências e segurança

- `confirmed_from_bytes`: metadados calculados do arquivo recebido.
- `static_candidate`: vetor ou referência identificada estaticamente; **não**
  significa que a CPU tenha executado o código.
- `observed_execution: false`: requer trace do Mesen para mudar.
- O resultado traz `raw_sha256` (inclui copier header quando houver)
  e `sha256` do corpo da ROM (sem copier header).
- Cache JSON fica sob `UMK3_STUDIO_HOME/intelligence` (ou
  `~/.umk3-re-studio/intelligence`), por hash e versão do analisador.
- O cache armazena metadados, bancos, grafos e evidências, **não a ROM**.
- O job em andamento fica em memória; após reinício, reenvie a mesma ROM para
  reutilizar o resultado armazenado em cache.
- A API não tem autenticação: **execute apenas em localhost**. Não exponha
  `0.0.0.0`, port-forward, túnel público ou acesso remoto.
- Esta API não permite que uma IA externa consulte automaticamente seu PC.
  Na fase de conectividade, será necessário um conector autenticado ou
  pacotes de evidência sincronizados sem bytes de ROM.

## Limitações intencionais

- Ainda não conectado ao importador da interface principal. Na Fase 2, o
  frontend poderá usar este serviço após o upload ou o servidor principal
  poderá delegar a análise ao orquestrador.
- Análises de gráficos, DMA real, dumps WRAM, símbolos MLB e Hidden Roster
  dependem de integração posterior e/ou arquivos adicionais.
- Não interpreta automaticamente toda a ROM como código, evitando erros por
  bytes de gráficos ou dados.
- Progresso é consultado por polling; SSE/WebSocket é uma etapa futura.
- Sem acesso a snapshots de memória nem a execução em emulador.
- Tarefas em andamento compartilham limite de dois workers e não sobrevivem
  ao reinício do processo; `completed` é restaurado pelo cache.

## Testes

```powershell
python -m pytest -q tests/test_intelligence_core.py
python -m pytest -q
```

## Próximas fases

1. Integrar ao fluxo atual de importação de projetos, sem duplicar cópia de ROM.
2. Conectar gradualmente os motores de extração gráfica, símbolos e correlação.
3. Adicionar SSE, cancelamento, quotas por projeto e persistência de jobs.
4. Criar acesso externo apenas mediante autenticação e controles explícitos.
