# ROM Patch Lab — comparação e patches IPS

Ferramenta isolada, sem dependências adicionais nem alterações na API. Funciona
em paralelo ao Hidden Roster Analyzer v2.

## Escopo

- Identifica tamanho, presença de cabeçalho copier de 512 bytes e SHA-256.
- Compara duas ROMs do mesmo tamanho; apresenta quantidade de bytes e regiões alteradas.
- Gera **IPS** com offsets físicos de arquivo (não endereços CPU 65C816).
- Faz **round-trip**: aplica o IPS somente em memória para verificar igualdade com a ROM modificada.
- Pode verificar um IPS contra o SHA-256 esperado, sem gravar uma ROM derivada.
- Recusa sobrescrever um arquivo de patch/relatório já existente.

Nenhuma ROM é distribuída ou incorporada ao repositório. Use apenas arquivos de
ROM que você tenha autorização para manipular.

## Comandos PowerShell

Execute a partir da raiz do repositório:

```powershell
python -m tools.rom_patch_lab inspect ".\original.sfc"

python -m tools.rom_patch_lab diff ".\original.sfc" ".\modificada.sfc" `
  --ips ".\mudancas.ips" --report ".\mudancas.json"

python -m tools.rom_patch_lab verify ".\original.sfc" ".\mudancas.ips" `
  --expected-sha256 "COLE_O_SHA256_DA_ROM_MODIFICADA"
```

O comando `diff` cria os arquivos de saída somente quando os caminhos ainda não
existem. Nem `diff` nem `verify` modificam as ROMs de entrada.

## Cuidados técnicos

- IPS não inclui SHA-256 da ROM-base. Para distribuição segura, compartilhe
  o hash de base e o hash esperado do resultado juntamente com o IPS.
- IPS usa offsets de **24 bits** e limita registros a 65.535 bytes.
- O marcador `EOF` de IPS colide com o offset físico `0x454F46`;
  o codificador trata esse caso incluindo o byte anterior no registro.
- Não são suportados redimensionamento, registros RLE de geração, IPS com
  metadados de truncamento nem comparação de ROMs com tamanhos diferentes.
  O leitor aceita registros RLE convencionais.
- Para comparar ROMs com e sem copier header, normalize cópias separadamente
  antes da comparação. O programa não altera ou remove cabeçalhos sozinho.
- A ferramenta **não modifica a ROM** e não substitui testes de jogabilidade
  no Mesen.

## Testes

```powershell
python -m pytest -q tests/test_rom_patch_lab.py
python -m pytest -q
```

## Coexistência com trabalho paralelo

Esta entrega modifica somente:
- `tools/rom_patch_lab.py`
- `tests/test_rom_patch_lab.py`
- `docs/ROM_PATCH_LAB.md`

Não toca em `backend/server.py`, `backend/hidden_roster_analyzer.py`,
`backend/trace65816.py`, `backend/static/index.html` ou nos arquivos
de instrumentação do Mesen.
