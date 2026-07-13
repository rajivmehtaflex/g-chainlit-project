#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f chainlit.pid ]; then
  echo "No chainlit.pid found, nothing to stop"
  exit 0
fi

PID="$(cat chainlit.pid)"
if kill -0 "$PID" 2>/dev/null; then
  # start.sh launches via setsid, so PID is also the process group id;
  # killing just the PID leaves the chainlit child holding the port.
  kill -- "-$PID"
  echo "Stopped chainlit (PID $PID)"
else
  echo "Process $PID not running"
fi
rm -f chainlit.pid
