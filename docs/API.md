# API REST

Documentação OpenAPI gerada em tempo de execução: http://127.0.0.1:8000/docs.

- `GET /api/status`: sessão ativa e cabeçalho da ROM.
- `POST /api/projects`, `GET /api/projects`, `POST /api/projects/{pid}/open`: projetos SQLite.
- `POST /api/rom`, `/api/compare`, `/api/cdl`, `/api/mlb`: importar arquivos locais.
- `GET /api/disasm`, `/api/graph`, `/api/xrefs`: desmontagem e navegação.
- `GET /api/mlb/export`: exporta **todos** os símbolos de um projeto, sem limite do preview.
- `POST /api/dma/trace`, `GET /api/dma/trace/analyze`: importar eventos e analisar.
- `POST /api/capture/convert`, `GET /api/capture/audit`: converter logs Mesen.
- `POST /api/research/pair`: testar uma janela de dados por codec experimental.
- `POST /api/research/scan`: varredura limitada por intervalo, codec e passo.
- `GET /api/research/profile`: entropia e distribuição de bytes.

Todos os resultados de compressão são hipóteses, não resultados confirmados de decodificação proprietária. API local, sem autenticação; não exponha em rede.
