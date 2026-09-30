#!/usr/bin/env bash
# Start the Kate Foresight demo: API on http://localhost:8000, frontend on http://localhost:5173
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  echo "Creating virtualenv..."
  "$PY" -m venv .venv
fi
.venv/bin/pip install -q -r backend/requirements.lock

if [ ! -f backend/.env ]; then
  echo "Creating backend/.env from .env.example with generated secrets..."
  .venv/bin/python - <<'PYEOF'
import secrets, pathlib
src = pathlib.Path("backend/.env.example").read_text()
jwt_secret = secrets.token_urlsafe(48)
demo_password = "kate-" + secrets.token_hex(4)
out = src.replace("JWT_SECRET=\n", f"JWT_SECRET={jwt_secret}\n").replace("DEMO_PASSWORD=\n", f"DEMO_PASSWORD={demo_password}\n")
pathlib.Path("backend/.env").write_text(out)
print(f"  demo password for every persona and admin: {demo_password}  (stored in backend/.env, git-ignored)")
PYEOF
fi

if [ ! -f backend/data/customers.json ]; then
  (cd backend && ../.venv/bin/python data/generate.py)
fi

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd backend && ../.venv/bin/uvicorn api:app --host 127.0.0.1 --port 8000 --reload) &
(cd frontend && ../.venv/bin/python -m http.server 5173 --bind 127.0.0.1) &

echo
echo "API:      http://localhost:8000/health"
echo "Frontend: http://localhost:5173"
echo "Personas: lien, marc, rita, admin  (password: DEMO_PASSWORD in backend/.env)"
echo "Ctrl+C stops both."
wait
