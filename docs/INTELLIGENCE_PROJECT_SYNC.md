# UMK3 Intelligence Core — Fase 2: sincronização com projetos

A API independente na porta `3091` agora lê o banco de projetos do Studio
e detecta automaticamente ROMs importadas pela interface principal.
**Não precisa importar a ROM duas vezes.**

## Como usar no Windows

Abra dois terminais PowerShell na pasta do repositório atualizado.

Terminal 1 — Studio original:

```powershell
python -m uvicorn backend.server:app --host 127.0.0.1 --port 3080
```

Terminal 2 — Intelligence Core:

```powershell
python -m uvicorn backend.intelligence_api:app --host 127.0.0.1 --port 3091
```

Abra o Studio em `http://127.0.0.1:3080` e a documentação do
Intelligence Core em `http://127.0.0.1:3091/docs`.

1. No Studio, **crie ou abra um projeto** antes de importar a ROM.
2. Importe a ROM normalmente pela interface principal.
3. O Intelligence Core consulta periodicamente o índice SQLite de projetos,
   detecta a alteração no `rom_sha` e agenda a análise do artefato existente.
4. Consulte `GET /api/intelligence/projects`, localize o `project_id` e
   depois abra `GET /api/intelligence/projects/{pid}/summary`.
5. Se desejar iniciar/verificar sem aguardar o próximo ciclo,
   use `POST /api/intelligence/projects/{pid}/analyze`.

O intervalo padrão é 3 segundos. Para alterar:
```powershell
$env:UMK3_INTELLIGENCE_POLL_SECONDS="1"
python -m uvicorn backend.intelligence_api:app --host 127.0.0.1 --port 3091
```

Se a API 3091 já está em execução, interrompa com Ctrl+C **nesse terminal**
e inicie a versão atualizada. `--reload` não é necessário.

## Endpoints novos

| Método | Endpoint | Descrição |
| --- | --- | --- |
| GET | `/api/intelligence/projects` | Projetos com situação de análise |
| GET | `/api/intelligence/projects/{pid}` | Status, job e etapas |
| POST | `/api/intelligence/projects/{pid}/analyze` | Reanalisar/forçar detecção |
| GET | `/api/intelligence/projects/{pid}/summary` | Resumo estático da ROM |
| GET | `/api/intelligence/projects/{pid}/evidence` | Evidências paginadas |

Os endpoints por job da Fase 1 permanecem disponíveis.

## Separação de responsabilidades e segurança

- Integração é **somente leitura** no que diz respeito ao banco de projetos
  e aos artefatos persistidos pelo Studio.
- Apenas o cache JSON de análises é gravado, sem copiar os bytes da ROM.
- Os artefatos são validados por SHA-256 antes da análise.
- A substituição da ROM muda a associação do projeto para um novo job.
- Análises são compartilhadas por SHA, evitando duplicar trabalho entre
  projetos com a mesma ROM.
- O watcher examina até quatro projetos por ciclo, em rodízio.
- Sem projeto salvo, não há sincronização automática. Carregar ROM apenas
  em sessão temporária continua exigindo o endpoint `/import` da Fase 1.
- A API continua **sem autenticação**. Use exclusivamente `127.0.0.1`.
  Ela não dá ao ChatGPT acesso remoto direto ao seu PC.
- O serviço não toca no parser do Claude, no `backend/server.py` nem na
  interface principal do Studio.
- Para vários processos Uvicorn/workers, cada processo teria seu próprio
  watcher. Use **um único worker** nesta fase.

## Testes

```powershell
python -m pytest -q tests/test_intelligence_projects.py
python -m pytest -q
```

## Fase 3 planejada

Unificar os resultados de símbolos MLB, dumps de WRAM, DMA, gráficos e
rastreamentos do Mesen em um modelo de evidências com proveniência e graus
de confiança, sem confundir análise estática com execução observada.
