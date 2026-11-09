# UMK3 Reverse Engineering Studio — v0.1 (MVP funcional)

Aplicação **local e de leitura** para análise de ROMs Super Nintendo, especialmente Ultimate Mortal Kombat 3 Deluxe 2.2. **Nenhuma ROM é distribuída no pacote.** Utilize os seus próprios arquivos.

## Instalar no Windows

1. Instale Python 3.12 ou superior e marque a opção **Add Python to PATH**.
2. Extraia este ZIP numa pasta local, por exemplo `C:\UMK3-RE-Studio`.
3. Execute **`iniciar-windows.cmd`**. Na primeira execução, o script instala as dependências Python usando o pip. A instalação exige acesso à internet; depois disso, o aplicativo roda localmente.
4. Acesse **http://127.0.0.1:8000** se o navegador não abrir automaticamente.
5. Em *Projeto e arquivos*, selecione a sua ROM Deluxe `.sfc` ou o dump `SnesPrgRom.dmp`.
6. Opcional: importe a ROM original para comparação, o `.cdl` e o `.mlb` que você exportou do Mesen 2.

**Windows PowerShell manual:**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Se a política do PowerShell bloquear `Activate.ps1`, use `iniciar-windows.cmd` em vez de alterar a política do sistema.

Linux: `./iniciar-linux.sh`.

## Primeiro teste recomendado

1. Importe `SnesPrgRom.dmp` (8 MiB). O painel deve indicar **ExHiROM**, título `SNESFOREVER.COM.BR` e checksum `DE7A`.
2. Digite **`08A53C`** em *ROM offset*, pressione **Analisar** e verifique `5C 62 5E D0` → `JML $D05E62`.
3. Ou digite `C8:A53C` em *Endereço CPU* e pressione **Ir**.
4. Teste `408738` para ver o trampolim `REP #$30`, `PHA`, `PHX`, `PHY`, `PHD`, `PHB`, `JML $808743`.
5. Importe o CDL (`CDLv2`), a seguir o MLB do Mesen, para visualizar marcações e símbolos.

## O que já funciona

- Importação da ROM por upload para o servidor local; cabeçalho copier opcional de 512 bytes.
- Cabeçalho interno, título, checksum, hash SHA-256, CRC32, mapeamento HiROM/LoROM/ExHiROM.
- Conversão de endereço CPU ↔ offset ROM com regiões não-ROM rejeitadas; note que endereços espelhados podem ter mais de uma representação válida.
- Mapa de 64 KiB por banco (128 bancos na Deluxe), bytes 00/FF, diferenças e cobertura CDL.
- Viewer hexadecimal em leitura, com diferenças frente à segunda ROM destacadas.
- Desmontador com matriz de **256 opcodes 65C816**, modos de endereçamento e operandos; estado M/X alterado por REP/SEP e marcado como desconhecido em PLP/RTI/XCE.
- Navegação simples por endereços, instruções e destinos diretos.
- Basic blocks limitados e endpoint de CFG conservador `/api/graph`.
- Parser do **CDL Mesen `CDLv2`** usado na captura, com contagem de código/dados/total.
- Importação de labels MLB, pesquisa, labels manuais e exportação MLB.
- API HTTP local com documentação em `/docs` e testes `pytest`.

## Limitações (não implementado ainda)

- **Não é uma descompilação completa** do UMK3. O fluxo de M/X exige rastreamento de estados por caminho, e indireções/interrupções necessitam de análise adicional. O disassembler linear mostra bytes após saltos, mas eles **não devem ser automaticamente considerados código**.
- O byte CDL é interpretado de forma conservadora: bit 0 como código e bit 1 como dados; outros bits ficam disponíveis para inspeção, sem inferências de uso.
- O grafo de chamadas não reconstrói automaticamente todos os saltos indiretos, jump tables, DBR, DP, nem fluxos de retorno.
- Os labels manuais permanecem apenas na memória da sessão do servidor até serem exportados; **SQLite e persistência multi-projeto são trabalho da versão seguinte**.
- A interface funciona sem npm ou compilação de frontend. Este MVP usa **HTML/CSS/JS locais** para simplificar a instalação; migração para React/TypeScript continua planejada.
- Não é um editor binário nem gera ROMs modificadas. Não executa jogos, emulador ou traces.
- Valores dos personagens encontrados anteriormente são **candidatos** e não funções de seleção confirmadas.

## Arquitetura

- `backend/core.py`: parser ROM, mapeamento, CDL/MLB, disassembler, CFG.
- `backend/server.py`: FastAPI, sessões e endpoints.
- `backend/static/index.html`: UI local.
- `tests/`: testes unitários e integração.

## Testar

```bash
python -m pytest -q
```

## Segurança

API escuta apenas em `127.0.0.1` por padrão. Não execute com `--host 0.0.0.0` em redes não confiáveis: a API recebe arquivos binários locais, mantém dados na memória e não implementa autenticação. Evite incluir ROMs comerciais em repositórios públicos.
