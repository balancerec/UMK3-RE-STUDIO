# Instalação e execução

## Requisitos
Python 3.12+, Windows 10/11 ou Linux, navegador atualizado. As dependências de `requirements.txt` são instaladas na primeira configuração, com internet.

## Windows
Na raiz do projeto, execute `iniciar-windows.cmd`. Alternativamente:

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000.

## Linux
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
```

## Dados locais
Banco SQLite e artefatos ficam em `~/.umk3-re-studio` ou no caminho definido por `UMK3_STUDIO_HOME`. Preserve backups. Não coloque ROMs, dumps, credenciais nem arquivos pessoais no Git.

## Testes
`python -m pytest -q`. Testes locais não substituem um teste visual no Windows e no emulador Mesen 2.
