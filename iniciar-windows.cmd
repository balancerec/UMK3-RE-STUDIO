@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist .venv ( %PY% -m venv .venv || goto :fail )
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt || goto :fail
start "" http://127.0.0.1:8000
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
goto :end
:fail
echo ERRO! Verifique se o Python 3.12+ esta instalado.
pause
:end
