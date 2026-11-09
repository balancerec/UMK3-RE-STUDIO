# UMK3 Reverse Engineering Studio — v0.4

Aplicativo **local** para investigação de ROMs SNES e **Ultimate Mortal Kombat 3 Deluxe 2.2**. Evolução compatível com as versões v0.1–v0.3; não inclui ROMs comerciais. Interface HTML/CSS/JS local e API FastAPI/Python. A conexão com a internet só é necessária na primeira instalação de dependências Python.

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

## v0.3 — Memory Analyzer e Character Mapper

Nova aba **Memory Analyzer**. Crie ou abra um projeto SQLite e importe capturas de 128 KiB `SnesWorkRam.dmp` ou de 16 MiB `SnesMemory.dmp`. O sistema extrai os bancos físicos `$7E/$7F` e persiste os dumps em armazenamento por SHA-256; capturas de projetos diferentes ficam separadas.

Recursos entregues:
- Importação com nome do personagem e ID hexadecimal **opcional** (anotação, não conclusão).
- Comparação de duas capturas com filtros de offset e extensão, diferenças por byte e páginas.
- Busca por campos discriminantes entre várias capturas; capturas repetidas do mesmo lutador descartam endereços instáveis.
- Classificação pelo número de coincidências com IDs informados, com prioridade para `$7E:36D0`, `$7E:52C8`, `$7E:1C59`.
- Recomendações de breakpoints de escrita para Mesen 2; nenhum controle remoto do emulador é realizado.
- Lista de capturas persistente com exclusão individual. Nenhuma ROM é alterada.

**Limitação importante:** um campo que contém IDs esperados em snapshots pode ser somente uma cópia transitória; sua função precisa de prova por trace, comparação durante a transição e breakpoint de escrita. Não interpretar a lista automática como tabela de IDs confirmados.

### Testes

`python -m pytest -q` — 18 testes, incluindo integração da API e persistência SQLite. Sintaxe do JavaScript validada com `node --check`.

### Instalação

A aplicação ainda usa FastAPI com frontend HTML/JS local, conforme as versões anteriores. Execute `iniciar-windows.cmd` com Python 3.12+ ou `iniciar-linux.sh`. Acesse http://127.0.0.1:8000, abra projeto, importe ROM quando desejar e use a aba **Memory Analyzer**. A análise de WRAM não exige ter ROM aberta.


## v0.4 — Graphics Explorer

Nova aba **Graphics Explorer**, mantendo as demais funcionalidades da v0.3.

### Importação

- **SnesVideoRam.dmp**: exatamente 65.536 bytes (64 KiB).
- **SnesCgRam.dmp**: exatamente 512 bytes, 256 cores BGR555.
- **SnesSpriteRam.dmp**: exatamente 544 bytes, OAM baixa de 512 bytes e alta de 32 bytes.

Arquivos são guardados por projeto no SQLite (metadados) e em armazenamento SHA-256 (conteúdo); ao reabrir o projeto voltam a ficar disponíveis. Também funciona sem projeto, apenas durante a sessão.

### Tile Viewer

- Decodificação planar padrão SNES **2bpp, 4bpp, 8bpp** (8x8 pixels por tile).
- Offset da VRAM em **bytes hexadecimais**, alinhado a 16/32/64 bytes por tile.
- Seleção de subpaleta CGRAM, quantidade de linhas/colunas, escala e grade.
- Geração e exportação real de imagens PNG (recurso de leitura apenas).
- A VRAM não é um spritesheet e a ordem de tiles só ganha significado quando a tabela de composição é identificada.

### CGRAM / Paletas

- Tabela interativa de 256 cores com conversão **BGR555 → RGB888**; identificação por índice.
- Não reescreve CGRAM nem ROM; a edição interativa de paletas ficará para versão futura.

### OAM / Sprite Viewer

- 128 entradas OAM e seus bits auxiliares para X de 9 bits e tamanho de OBJ.
- Posição, tile, prioridade, subpaleta, flips e tabela de nome.
- Composição aproximada de objetos 4bpp em RGBA com transparência e PNG.
- Campos configuráveis para OBSEL size mode, base de gráficos OBJ e name-select (offsets VRAM em bytes hexadecimais).
- **A captura não inclui os registradores PPU**: a base VRAM, name-select e size mode não são recuperados automaticamente. O resultado pode mostrar sprites fragmentados ou incorrectos; a reconstrução final depende dos registradores da mesma captura.
- Sem BG layers, janela, scanline timing nem raster effects. Não identifica automaticamente personagens ou quadros de animação.

### Endpoints adicionais

- `POST /api/graphics/{vram|cgram|oam}`
- `GET /api/graphics/status`
- `GET /api/graphics/palette`
- `GET /api/graphics/oam`
- `GET /api/graphics/tiles.png`
- `GET /api/graphics/sprites.png`

Documentação interativa em `http://127.0.0.1:8000/docs`.

### Executar / validar

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

**Testes nesta versão:** 24 aprovados (inclui testes de API e decodificação gráfica; validação opcional com dumps enviados). JavaScript validado com `node --check`.

**Limites de segurança:** esta aplicação não altera ROMs ou dumps originais, não reconstrói automaticamente imagens de personagens inteiros e não descomprime recursos gráficos de formatos próprios ainda desconhecidos. Nenhuma ROM comercial ou dump pessoal está incluído no ZIP.

## v0.5 — Sprite Extraction Engine: investigação gráfica na ROM

A nova aba **Sprite Extraction Engine** foi adicionada sem remover os módulos anteriores. **Esta fase é investigativa; não há ainda um decodificador comprovado da compressão gráfica usada pelos lutadores de UMK3.** Nenhum recurso é modificado ou escrito na ROM.

### Recursos novos

- **Visualização planar da ROM**: interpretação *bruta* de offsets como tiles 2bpp, 4bpp ou 8bpp, com paleta CGRAM opcional. O PNG é gerado no servidor e pode ser salvo, mas não significa que aquele intervalo seja gráfico real.
- **Busca exata ROM ↔ VRAM**: procura janelas de 16, 32, 64, 128, 256 ou 512 bytes da VRAM diretamente nos bytes da ROM. Descarta janelas muito uniformes e limita resultados para evitar falsos positivos. Permite exportar resultados CSV.
- **Inventário dos bancos**: entropia Shannon, fração de bytes 00/FF, número de bytes distintos e maior repetição consecutiva. Esses indicadores **não** provam que os bancos estejam comprimidos ou livres.
- **Sequências repetidas**: lista trechos de bytes iguais com extensão configurável, apenas para investigação.
- **Navegação integrada**: resultados encontrados na pesquisa podem ser abertos diretamente na prévia de tiles da ROM.

### Procedimento recomendado

1. Na v0.5, crie/abra o projeto e importe `SnesPrgRom.dmp` (8 MiB).
2. No Graphics Explorer, importe `SnesVideoRam.dmp` (64 KiB) e `SnesCgRam.dmp` (512 bytes, opcional para prévia).
3. Abra **Sprite Extraction Engine** e selecione um banco, por exemplo offset `400000`.
4. Altere `bpp`, número de linhas e colunas; observe a prévia e exporte um PNG quando útil.
5. Execute a pesquisa ROM ↔ VRAM. O painel mostra quantas janelas foram consideradas, quantas foram descartadas por baixa diversidade e quais resultaram em correspondências exatas.
6. Registre os offsets candidatos e confirme com rastreamentos DMA e do carregador gráfico no Mesen 2. A ausência de correspondência é inconclusiva.

### API e testes

- `GET /api/extract/banks`
- `GET /api/extract/match?chunk_size=64&vram_offset=0&vram_length=4096&step=64&minimum_unique=12`
- `GET /api/extract/runs?start=4194304&length=65536&min_run=64`
- `GET /api/extract/preview.png?offset=4194304&bpp=4&columns=16&rows=8&palette=0`

`python -m pytest -q`: 29 testes (24 herdados e 5 novos). A sintaxe do JavaScript passa no `node --check`. Em uma busca exploratória com dados reais, nos primeiros 8 KiB da VRAM e diversidade mínima 12, **não surgiram correspondências exatas** em janelas de 32 ou 64 bytes da ROM. O resultado não confirma algoritmo de compressão.

### O que ainda falta

1. Capturar registradores PPU/OBSEL e rastreamentos DMA sincronizados com VRAM/CGRAM/OAM.
2. Identificar o carregador de gráficos e seus buffers via disassembler e breakpoints.
3. Descobrir e validar algoritmos de descompressão com pares de dados entrada/saída.
4. Localizar as tabelas de ponteiros e os metadados dos frames dos lutadores.
5. Montar animações completas por personagem e viabilizar reinserção segura.

O projeto distribui somente a aplicação e os testes. **As ROMs comerciais e os dumps do usuário não são incluídos no pacote.**
