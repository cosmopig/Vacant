#!/bin/bash
# enclosure **內部**：把 A 級的兩個探針各燒一次，然後把結果寫進工作區。
#
#   用法（由 run_attest.sh 呼叫）：attest_inner.sh <bin 目錄> <repo 根> <輸出目錄>
#
# 三個環境變數控制這一跑要不要製造負控制：
#   ENC_FIRE_CANARY=0   **不燒掛鉤**（＝掛鉤被拆掉的那一格）
#   ENC_ROGUE_CALL=1    **多打一通沒有任何工具事件的**（對帳的負控制）
#   VACANT_RUN_ID       這一跑的 id（canary 的 query 會帶它）
#
# ⚠ 這裡燒 canary 的方式是**直接呼叫契約**（`hookcli session_start`），
#   不是讓某個 agent 框架的掛鉤去呼叫它。兩者的差別要講清楚：本腳本證明
#   「契約與兩個探針在真的圍牆裡會動」，**不**證明「某個 agent 的掛鉤會燒」。
#   後者要那個 agent 真的跑一趟（`run_agent.sh`）。
set -u
BIN="$1"
REPO="$2"
OUTDIR="$3"
SOCK="${ENC_DOOR_SOCK:-/run/vacant/relay.sock}"
PORT="${ENC_DOOR_PORT:-8787}"
PY=/usr/bin/python3

mkdir -p "$OUTDIR"
export PYTHONPATH="$REPO"

# 門的 guest 端（圍牆裡面聽 TCP，轉給被 ro-bind 進來的 unix socket）
"$PY" "$BIN/door_guest.py" "$PORT" "$SOCK" > "$OUTDIR/door_guest.log" 2>&1 &
GP=$!
for _ in $(seq 1 25); do
  if "$PY" -c "import socket,sys
try:
    socket.create_connection(('127.0.0.1',$PORT),0.5).close(); sys.exit(0)
except Exception:
    sys.exit(1)"; then break; fi
  "$PY" -c "import time; time.sleep(0.2)"
done

export VACANT_RUN_PROXY="http://127.0.0.1:$PORT"
export VACANT_HOOK_LOG="$OUTDIR/hooks.jsonl"
export VACANT_HOOK_AGENT="${VACANT_HOOK_AGENT:-probe}"

# 探針一：圍牆。**在圍牆裡量，因為圍牆外面看不到圍牆裡的 netns。**
"$PY" -m vacant_network.vrun.attest --probe --out "$OUTDIR/probe_enc.json" \
    > /dev/null || echo "PROBE_FAILED" >> "$OUTDIR/errors.txt"

# 探針二：掛鉤 canary（會順手對門打一通 ⇒ 實證 proxy 真的在跑）
if [ "${ENC_FIRE_CANARY:-1}" = "1" ]; then
  "$PY" -m vacant_network.vrun.hookcli session_start < /dev/null
  echo "CANARY_INVOKED"
else
  echo "CANARY_SKIPPED（負控制：掛鉤被拆掉）"
fi

# 負控制：一通**沒有任何工具事件**的呼叫（有人直接對門打了一發）
if [ "${ENC_ROGUE_CALL:-0}" = "1" ]; then
  "$PY" - <<'PYEOF'
import os
import urllib.request
base = os.environ["VACANT_RUN_PROXY"].rstrip("/")
try:
    urllib.request.urlopen(base + "/v1/chat/completions", data=b"{}",
                           timeout=20).read()
    print("ROGUE_CALL_SENT")
except Exception as e:                                       # noqa: BLE001
    print(f"ROGUE_CALL_SENT_WITH_ERROR {type(e).__name__}: {e}")
PYEOF
fi

kill "$GP" 2>/dev/null
echo "ATTEST_INNER_DONE"
