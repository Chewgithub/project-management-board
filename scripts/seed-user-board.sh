#!/bin/sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SEED_FILE="${REPO_ROOT}/scripts/seed-user-board.json"
API_URL="http://localhost:8000/api/board/user"

if ! curl -sS -m 3 http://localhost:8000/api/ping >/dev/null; then
  echo "Backend is not reachable on http://localhost:8000."
  echo "Start it first with: ./scripts/run-backend-docker.sh"
  exit 1
fi

if [ ! -f "${SEED_FILE}" ]; then
  echo "Seed file not found: ${SEED_FILE}"
  exit 1
fi

curl -sS -X PUT "${API_URL}" \
  -H 'Content-Type: application/json' \
  -d @"${SEED_FILE}" >/tmp/pm-seed-response.json

python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/pm-seed-response.json').read_text())
board = payload['board']
print(f"Seeded board for user: {payload['username']}")
print(f"Columns: {len(board['columns'])}")
print(f"Cards: {len(board['cards'])}")
PY

echo "Open http://localhost:3000 and refresh to see seeded cards."
