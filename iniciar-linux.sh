#!/bin/sh
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
printf '\nAbra http://127.0.0.1:8000\n'
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
