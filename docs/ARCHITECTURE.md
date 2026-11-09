# Arquitetura de software — v1.0.1

O Studio é uma aplicação local, read-only, construída sobre Python/FastAPI, JavaScript e SQLite.

| Módulo | Responsabilidade |
|---|---|
| `backend/core.py` | Detecção de ROM, HiROM/ExHiROM, checksum, CDL/MLB, instruções 65C816 |
| `backend/analysis.py` | CFG e referências diretas |
| `backend/storage.py` | Projetos SQLite, símbolos e arquivos endereçados por SHA-256 |
| `backend/memory.py` | Comparação WRAM e candidatos de ID de personagens |
| `backend/graphics.py` | Tiles SNES, CGRAM, OAM e PNG |
| `backend/extraction.py` | Bancos, padrões, correspondências ROM/VRAM |
| `backend/dma.py` | Assinaturas de registradores e buffers candidatos |
| `backend/dma_trace.py` | Reconstituição conservadora de DMA |
| `backend/capture.py` | Conversão e auditoria dos logs Mesen |
| `backend/correlation.py` | Correlação PC/offset ROM/CDL |
| `backend/decompression.py` | Testes genéricos e limitados de RLE/PackBits |
| `backend/server.py` | Endpoints e estado ativo da aplicação |
| `backend/static/index.html` | Interface gráfica |

### Dados
ROM e dumps fornecidos pelo usuário → API FastAPI → SHA-256/SQLite → análises read-only → respostas JSON/PNG/CSV.

### Precisão do CPU
O PC de execução do 65C816 tem 16 bits e avança dentro do PBR atual. Um fetch em `$C0:FFFF` continua em `$C0:0000`, não em `$C1:0000`. O código usa `next_instruction_offset` e `_instruction_bytes` para essa condição. A propagação E/M/X é conservadora e não resolve todos os caminhos condicionais.

### Modelo de uso e risco
A sessão ativa da API é **global em memória**. Destina-se a **uma pessoa usando localhost**; não suporta isolamento de múltiplos usuários/abas. Não exponha `uvicorn` em `0.0.0.0` nem publique a porta sem autenticação, isolamento por sessão e controles de acesso. Não há execução automática de scripts enviados à API.

### Limites atuais
Sem reconstrução byte-identical, sem reinserção de sprites, sem codec UMK3 confirmado e sem análise de fluxo completa de todos os saltos indiretos.
