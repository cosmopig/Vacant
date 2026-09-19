#!/bin/bash
# enclosure **內部**：先把門的 guest 端拉起來，再跑 `ops/vacantrun/wrap_agent.sh`。
#
# 用法（由 run_agent.sh 呼叫）：inner.sh <agent> <wrap_agent.sh 路徑> <bin 目錄>
set -u
AGENT="$1"
WRAP="$2"
BIN="$3"
SOCK="${ENC_DOOR_SOCK:-/run/vacant/relay.sock}"
PORT="${ENC_DOOR_PORT:-8787}"

/usr/bin/python3 "$BIN/door_guest.py" "$PORT" "$SOCK" > /tmp/door_guest.log 2>&1 &
GP=$!
for _ in $(seq 1 25); do
  if /usr/bin/python3 -c "import socket,sys
try:
    socket.create_connection(('127.0.0.1',$PORT),0.5).close(); sys.exit(0)
except Exception:
    sys.exit(1)"; then break; fi
  /usr/bin/python3 -c "import time; time.sleep(0.2)"
done

export VACANT_RUN_PROXY="http://127.0.0.1:$PORT"
export ANTHROPIC_BASE_URL="http://127.0.0.1:$PORT"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-vacant-run}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-vacant-run}"
export VACANT_AGENT_MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"
export VACANT_CODEX_REASONING_EFFORT="${VACANT_CODEX_REASONING_EFFORT:-none}"
export VACANT_HERMES_BIN="${VACANT_HERMES_BIN:-/var/tmp/vacant_hermes/hv/bin/hermes}"
export CI=1 TERM=dumb NO_COLOR=1

PROMPT="${ENC_PROMPT:-Create a file named solution.py in the current working directory. Its entire contents must be exactly these two lines:
def add(a, b):
    return a + b
Do not create any other file. Stop as soon as solution.py exists.}"

echo "--- agent stdout/stderr ---"
timeout "${ENC_AGENT_TIMEOUT:-300}" "$WRAP" "$AGENT" "$PROMPT" 2>&1 | tail -40
echo "agent_pipe_rc=${PIPESTATUS[0]}"
kill $GP 2>/dev/null
echo "--- door_guest.log ---"; tail -3 /tmp/door_guest.log
