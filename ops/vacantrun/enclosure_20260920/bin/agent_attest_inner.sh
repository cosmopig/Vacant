#!/bin/bash
# enclosure **內部**：門的 guest 端 → 圍牆探針 → **真 agent（掛鉤裝在裡面）**
# →（負控制）多打一通沒有工具事件的。
#
#   用法（由 run_agent_attest.sh 呼叫）：
#     agent_attest_inner.sh <bin 目錄> <repo 根> <輸出目錄> <agent> <prompt...>
#
# ⚠ 這支跟 `attest_inner.sh` 的差別**就是 A 級那一句話的全部**：
#   `attest_inner.sh` 的 canary 是**直接呼叫契約**（`hookcli session_start`）；
#   這一支**沒有任何一行以事件參數執行 `hookcli`**（去掉註解後 grep ＝ 0；
#   同一支 grep 在 `attest_inner.sh` 上是 1＝正控制），canary 只可能由
#   **agent 框架自己的掛鉤**燒起來。
#   ⚠ 唯一的例外要講明白：`timing` 那一格有一行
#   `python3 -c "import vacant_network.vrun.hookcli"`——**bare import**，
#   不呼叫 `handle()`／`emit()`，一筆事件都不寫、一通 canary 都不打。
#   所以這一支的 `canary_fired=true` 是「agent 的掛鉤燒的」，不是我們手動燒的。
#
# 環境變數（由 `enc.sh --setenv` 帶進來，**值裡不可以有空白**）：
#   VACANT_HOOK_LOG   掛鉤契約的日誌（`wrap_agent.sh` 看到它才會裝掛鉤）
#   VACANT_RUN_ID     這一跑的 id
#   VACANT_PI_DIAG    pi extension 的診斷線（跟契約日誌分開）
#   ENC_ROGUE_CALL=1  多打一通**沒有任何工具事件**的（對帳的負控制）
#   ENC_TIMING_ONLY=1 只量掛鉤冷啟動＋canary 往返，不跑 agent
set -u
BIN="$1"; REPO="$2"; OUTDIR="$3"; AGENT="$4"; shift 4
PROMPT="$*"
SOCK="${ENC_DOOR_SOCK:-/run/vacant/relay.sock}"
PORT="${ENC_DOOR_PORT:-8787}"
PY=/usr/bin/python3

mkdir -p "${OUTDIR}"
export PYTHONPATH="${REPO}"

# ── 門的 guest 端。**「起來了」＝真的連一次**，不是看行程在不在 ──────────
"$PY" "$BIN/door_guest.py" "$PORT" "$SOCK" > "$OUTDIR/door_guest.log" 2>&1 &
GP=$!
GUEST_OK=0
for _ in $(seq 1 40); do
  if "$PY" -c "import socket,sys
try:
    socket.create_connection(('127.0.0.1',$PORT),0.5).close(); sys.exit(0)
except Exception:
    sys.exit(1)"; then GUEST_OK=1; break; fi
  "$PY" -c "import time; time.sleep(0.2)"
done
echo "DOOR_GUEST_ALIVE=${GUEST_OK}"
if [ "$GUEST_OK" != "1" ]; then
  echo "門的 guest 端起不來 ⇒ agent 會拿到 Cannot connect to API 而 rc 仍是 0。停。" >&2
  echo "--- door_guest.log ---" >&2; cat "$OUTDIR/door_guest.log" >&2
  kill "$GP" 2>/dev/null
  exit 3
fi

export VACANT_RUN_PROXY="http://127.0.0.1:$PORT"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-vacant-run}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-sk-vacant-run}"
export ANTHROPIC_BASE_URL="$VACANT_RUN_PROXY"
export VACANT_AGENT_MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"
export VACANT_HOOK_AGENT="$AGENT"
export CI=1 TERM=dumb NO_COLOR=1

# ── 探針一：圍牆。**在圍牆裡量**，因為圍牆外面看不到圍牆裡的 netns ──────
"$PY" -m vacant_network.vrun.attest --probe --out "$OUTDIR/probe_enc.json" \
    > /dev/null || echo "PROBE_FAILED" >> "$OUTDIR/errors.txt"

# ── 量具活著的正控制 ＋ `CANARY_TIMEOUT_S` 的實測值 ──────────────────────
# ⚠ 這一段**會打一通**到門上 ⇒ 只在 `ENC_TIMING_ONLY=1` 的那一格跑，
#   否則它會變成這一格對帳裡一通沒有回合開端的呼叫（＝我們自己造的假陽性）。
if [ "${ENC_TIMING_ONLY:-0}" = "1" ]; then
  "$PY" - "$OUTDIR" <<'PYEOF'
import json, os, pathlib, subprocess, sys, time, urllib.request
out = pathlib.Path(sys.argv[1])
rec = {}
# (a) 圍牆裡冷啟動一個 python 要多久（hook 子行程的固定成本）
t = []
for _ in range(3):
    t0 = time.time()
    subprocess.run([sys.executable, "-c", "pass"], check=False)
    t.append(time.time() - t0)
rec["python_spawn_s"] = t
# (b) `import vacant_network.vrun.hookcli` 要多久（真正的冷啟動成本）
t = []
for _ in range(3):
    t0 = time.time()
    subprocess.run([sys.executable, "-c",
                    "import vacant_network.vrun.hookcli"], check=False)
    t.append(time.time() - t0)
rec["hookcli_import_s"] = t
# (c) canary 那一通的往返（`CANARY_TIMEOUT_S` 管的就是這一段）
base = os.environ["VACANT_RUN_PROXY"].rstrip("/")
t = []
for i in range(3):
    t0 = time.time()
    try:
        urllib.request.urlopen(f"{base}/v1/models?vacant_canary=timing{i}",
                               timeout=30).read(4096)
        t.append(round(time.time() - t0, 3))
    except Exception as e:                                   # noqa: BLE001
        t.append(f"{type(e).__name__}: {e}")
rec["canary_roundtrip_s"] = t
(out / "timing.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
print("TIMING " + json.dumps(rec, ensure_ascii=False))
PYEOF
  kill "$GP" 2>/dev/null
  echo "AGENT_ATTEST_INNER_DONE timing"
  exit 0
fi

# ── 真 agent。**掛鉤由 `wrap_agent.sh` 在這個行程樹裡裝**，
#    所以 canary 只可能是 agent 框架自己燒的 ────────────────────────────
echo "--- agent stdout/stderr ---"
timeout "${ENC_AGENT_TIMEOUT:-420}" "$REPO/ops/vacantrun/wrap_agent.sh" \
    "$AGENT" "$PROMPT" 2>&1 | tail -40
echo "agent_pipe_rc=${PIPESTATUS[0]}"

# ── 負控制：一通**沒有任何工具事件**的呼叫 ───────────────────────────────
if [ "${ENC_ROGUE_CALL:-0}" = "1" ]; then
  "$PY" - <<'PYEOF'
import os
import urllib.request
base = os.environ["VACANT_RUN_PROXY"].rstrip("/")
try:
    urllib.request.urlopen(base + "/v1/chat/completions", data=b"{}",
                           timeout=30).read()
    print("ROGUE_CALL_SENT")
except Exception as e:                                       # noqa: BLE001
    print(f"ROGUE_CALL_SENT_WITH_ERROR {type(e).__name__}: {e}")
PYEOF
fi

echo "--- 工作區 ---"
ls -la "$HOME" | head -20
kill "$GP" 2>/dev/null
echo "--- door_guest.log（尾 3 行）---"; tail -3 "$OUTDIR/door_guest.log"
echo "AGENT_ATTEST_INNER_DONE $AGENT"
