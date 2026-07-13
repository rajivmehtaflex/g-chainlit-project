#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f chainlit.pid ] && kill -0 "$(cat chainlit.pid)" 2>/dev/null; then
  echo "Already running with PID $(cat chainlit.pid)"
  exit 0
fi

CHAINLIT_PORT="$(grep -E '^CHAINLIT_PORT=' .env | cut -d '=' -f2)"

setsid nohup uv run chainlit run main.py --host 0.0.0.0 --port "${CHAINLIT_PORT}" --headless \
  > chainlit.log 2>&1 &
echo $! > chainlit.pid
disown

echo "Started chainlit on port ${CHAINLIT_PORT} (PID $(cat chainlit.pid)), logs in chainlit.log"
