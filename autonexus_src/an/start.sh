#!/usr/bin/env bash
# AUTONEXUS AI 2.0 — quick local start
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "No .env found. Copying .env.example → .env"
  cp .env.example .env
  echo "Edit .env and set JWT_SECRET + OWNER_PASSWORD_HASH before production use."
  echo "Demo credentials (after setting hash): owner@autonexus.local / autonexus-demo-2026"
fi

# Ensure data exists
python3 -c "
from pathlib import Path
needed = ['warehouses.csv','suppliers.csv','technicians.csv','documents.csv']
missing = [f for f in needed if not (Path('data')/f).is_file()]
if missing:
    print('Generating missing sample CSVs...')
    from autonexus.gen_csv import generate
    print(generate('data'))
else:
    print('Sample CSV data present.')
"

export PATH="$HOME/.local/bin:$PATH"
echo "Starting AUTONEXUS on http://127.0.0.1:8000"
echo "  Dashboard : http://127.0.0.1:8000/"
echo "  Living World: http://127.0.0.1:8000/world"
echo "  API docs  : http://127.0.0.1:8000/docs"
exec python3 -m uvicorn autonexus.api:app --host 127.0.0.1 --port 8000 --reload
