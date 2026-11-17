# PC Engine Lab — status experimental local e baseline (2026-11-17)

> Importante: a branch `main` consultada no GitHub contém a aplicação de engenharia reversa, mas **não contém o diretório `pc-engine/` nem os bridges do laboratório local** na árvore publicada no momento desta revisão. Os itens abaixo descrevem resultados do **ambiente Windows informado pelo operador**, não funcionalidades incorporadas a `main`.

## Dois sistemas distintos

1. **Pesquisa de UMK3 SNES:** captura Mesen, análise de ROM/dumps, CFG, DMA, paletas e identificação de personagens. Preservar evidências e níveis de confiança por origem.
2. **PC Engine Lab experimental:** motor de combate C++ independente, executado localmente via FastAPI. Não demonstra equivalência com o código, timing, física ou hitboxes de UMK3.

## Componentes locais informados

| Componente | Estado reportado |
|---|---|
| `ng_headless` e execuções nativas | Funcionando no Windows |
| API `/api/engine/status`, `/api/engine/runs`, `/api/engine/compare` | Testadas localmente |
| Interativa `/api/engine/interactive/sessions` | Disponível em instalação local |
| Storage Manager V1/V1.1 | Instalado e inventário visual homologado |
| Retenção assistida V1.2 | Instalado; funcionamento confirmado pelo operador |
| Baseline V1.3 | **PASSOU**: seis execuções, três cenários, 100 frames cada |
| Integração visual HUD V0.4.0/V0.4.1 | Funcionando localmente, mas código não necessariamente versionado |
| Native Collision Bridge V0.4.2 | Planejado; dados geométricos reais ainda pendentes |

## Resultados medidos (baseline local)

| Cenário | Repetições | Frames em cada execução | Hash FNV-1a64 | Divergências |
|---|---:|---:|---|---:|
| neutral | 2 | 100 | `cd5af60db80f4d6f` | 0 |
| normal-hit | 2 | 100 | `61ed1dc7c646d7de` | 0 |
| projectile | 2 | 100 | `2799a93d0037676b` | 0 |

Cada par teve 100 snapshots comparados, `same_engine_binary=true`, `independent_native_runs=true`. Binário SHA-256 `1a55e73aed876f1108ef643c51525764a4f7f675b49b4f16a119ddde872faf65`. Relatório local: `Desktop/PC-Engine-Lab-Backups/baseline-v13.json`.

**Não colocar `baseline-v13.json` real no Git sem revisão de dados e autorização; não colocar dumps, ROMs, runs ou backups ZIP no Git.**

## Limpeza e recuperação de armazenamento

A limpeza integral realizada no ambiente Windows preservou 81 registros: 48 headless e 33 interativos. Antes da limpeza, 57 estavam ativos, 24 tinham sido arquivados manualmente. O procedimento criou e verificou quatro backups ZIP (331 arquivos ao todo por logs) e moveu os 57 ativos para o histórico, deixando 0/32 em cada engine naquele momento.

A retenção assistida **não faz limpeza automática**; recomenda arquivamento em lotes, com confirmação. O número de ativos pode mudar após novas simulações da baseline.

## Operação local, se o backend estiver instalado

```powershell
cd "C:\Users\balancerec\Desktop\MORTAL KOMBAT 3 ULTIMATE ENGENHARIA REVERSA STUDIO\UMK3-RE-STUDIO-Codex"
py -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Endpoint de status: `http://127.0.0.1:8000/api/engine/status`.
O proxy HUD funciona localmente na porta 8015. Não expor o backend à rede. Evitar concorrência de múltiplos processos nas operações de arquivamento.

## Limitação de documentação e promoção ao Git

Os hotfixes locais não foram automaticamente sincronizados a este repositório. Antes de publicar a engine, coletar `git status --short`, inventário de `pc-engine/` e `backend/`, separar código, testes, dados de trabalho e backups; abrir PR de código dedicado e preservar os artefatos sensíveis localmente.

Ver [Arquitetura](ARCHITECTURE.md), [Evidências](EVIDENCIAS.md) e [Roadmap de combate](PC_ENGINE_NATIVE_COMBAT_ROADMAP.md).
