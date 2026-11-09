# UMK3 Reverse Engineering Studio — v0.2

Aplicativo **local** para investigação de ROMs SNES e **Ultimate Mortal Kombat 3 Deluxe 2.2**. Evolução da v0.1; não inclui ROMs comerciais. Interface HTML/CSS/JS local e API FastAPI/Python. A conexão com a internet só é necessária na primeira instalação de dependências Python.

## Executar no Windows

1. Instale **Python 3.12+** (marque **Add Python to PATH**).
2. Extraia todo o ZIP em `C:\UMK3-RE-Studio` ou outra pasta gravável.
3. Execute `iniciar-windows.cmd`. Na primeira execução, o script prepara `.venv` e instala dependências.
4. Abra `http://127.0.0.1:8000` se o navegador não abrir.
5. **Crie o projeto antes de importar** a ROM: somente projetos nomeados persistem os arquivos; sessão temporária ainda funciona sem salvamento.
6. Importe `SnesPrgRom.dmp` ou sua ROM Deluxe `.sfc`, depois `.cdl`, `.mlb` e, se desejar, o original de 4 MiB para comparação.
7. Use **CFG / Xrefs** para seguir saltos e chamadas estáticas; o botão *Varrer referências* parte do offset visível.
8. Em **Personagens**, clique *Importar 15 observações históricas* para incluir os valores extraídos dos dumps anteriores, em dois endereços cada.

Se `iniciar-windows.cmd` abrir e fechar, execute pelo Prompt de Comando aberto dentro da pasta:

```bat
iniciar-windows.cmd
```

Para encerrar: `Ctrl+C` na janela que executa o servidor. O aplicativo escuta só em `127.0.0.1:8000`.

## Novidades v0.2

- **SQLite local** com projetos, símbolos e observações de personagens persistentes; ROM, comparação e CDL armazenados em arquivos identificados por SHA-256.
- **Reabertura de projetos** entre execuções da aplicação; caminho de dados: `%USERPROFILE%\.umk3-re-studio` no Windows ou `~/.umk3-re-studio` no Linux. Defina `UMK3_STUDIO_HOME` para alterar.
- **Referências cruzadas limitadas** para destinos estáticos diretos (`JSR`, `JSL`, `JMP`, `JML`, branches); percorre caminhos com controle de estados M/X, produz origens e destinos sem inventar nomes de função. `max_instructions` ajustável na API. O analisador não garante descoberta exaustiva.
- **CFG visual por tabela** com blocos e navegação por endereço.
- **Catálogo baseado nas 15 capturas** de memória disponibilizadas no projeto; dois campos candidatos `$7E:36D0` e `$7E:52C8`. Human Smoke continua rotulado como provável; o código não trata offsets como variáveis comprovadas.
- APIs documentadas em `http://127.0.0.1:8000/docs`, incluindo `/api/projects`, `/api/xrefs`, `/api/characters`.
- **Testes de persistência, análise estática e integração HTTP**, além dos testes herdados da v0.1.

## Recurso herdados da v0.1

- Leitura HiROM/ExHiROM/LoROM com cabeçalho copier opcional.
- Hashes, título, cabeçalho interno, checksum e mapa de bancos.
- Desmontagem linear com matriz dos 256 opcodes 65C816, REP/SEP e estado M/X.
- Hex viewer, comparação original/Deluxe, importação CDL e MLB e exportação de símbolos MLB.

## Exemplo de validação no jogo

1. Abra `SnesPrgRom.dmp` (8 MiB); confira ExHiROM e checksum `DE7A`.
2. Navegue ao offset `08A53C`; deve exibir `JML $D05E62` (bytes `5C 62 5E D0`).
3. No painel **CFG / Xrefs**, analise a partir desse offset; haverá referência direta ao offset `105E62`.
4. Navegue ao offset `408738` para examinar o trampolim de 65C816 na região expandida.

## Limitações importantes

- **Não é uma decompilação nem um projeto remontável**: nenhuma rotina de seleção foi semanticamente confirmada por trace.
- Referências cruzadas percorrem apenas **fluxos diretos**, e podem interpretar dados como código se a raiz estiver incorreta; estado M/X desconhecido interrompe o caminho. Endereços indiretos e dinâmica de bancos continuam pendentes.
- O conteúdo CDL é interpretado conservadoramente por bits de código/dado usados nas capturas.
- A análise de xrefs é calculada em memória e precisa ser executada de novo ao reabrir o projeto; ROM, CDL e símbolos persistem.
- A sessão do servidor é única. Não usar como serviço multiusuário ou expor na internet.
- Os valores da versão iOS são referência, não prova dos IDs de SNES; o ID `0x19` continua não identificado.
- Não grava patches nem altera a ROM original. O cadastro de personagens é somente leitura na interface nesta versão.

## Desenvolvedor

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Arquitetura: `backend/core.py` (ROM/65C816/CFG), `backend/analysis.py` (xrefs), `backend/storage.py` (SQLite), `backend/server.py` (API), `backend/reference/characters.csv` (observações), `backend/static/index.html` (interface) e `tests` (suíte).
