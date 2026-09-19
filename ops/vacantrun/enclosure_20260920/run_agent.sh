#!/bin/bash
# 一個 agent 在 enclosure 裡跑完一題，**而且門是會終結 HTTP 的 proxyd**。
#
#   bash ops/vacantrun/enclosure_20260920/run_agent.sh <pi|codex|opencode|claude|hermes>
#
# 前提：`run_probes.sh` 建好的門還活著，或這支自己起一扇（預設會自己起）。
# 產出：$ENC_BASE/out/agent_<name>.log ＋ agent_<name>.json（含門的逐通 path）。
#
# ⚠ 「通數 > 0」才算被中介到（`envmap` 誠實邊界 1）。這支印的 `door_calls`
#   讀的是**門自己的 journal**（`proxyd/wire/index.jsonl`），不是 agent 的 stdout。
set -u
AGENT="${1:?用法：run_agent.sh <pi|codex|opencode|claude|hermes>}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/bin"
REPO="${ENC_REPO:-$(cd "$HERE/../../.." && pwd)}"
WRAP="$REPO/ops/vacantrun/wrap_agent.sh"
BASE="${ENC_BASE:-/var/tmp/vacant-enclosure-20260920}"
UPSTREAM="${ENC_UPSTREAM:-http://100.86.226.21:1234}"
PY="${ENC_PY:-/usr/bin/python3}"
NODE="${ENC_NODE:-/home/user1/.local/opt/node-v22.23.2-linux-x64}"
OUT="$BASE/out"; DOOR="$BASE/door"; WS="$BASE/ws1/$AGENT"
JOURNAL="$BASE/state/relay/proxyd/wire/index.jsonl"
mkdir -p "$OUT" "$DOOR" "$BASE/state"
rm -rf "$WS"; mkdir -p "$WS"

# ⚠ **「socket 檔在」不等於「門活著」。** 2026-09-20 實際踩到：前一格的
#   proxyd 收到 SIGTERM 之後還沒把 socket 檔 unlink，下一格就用 `-S` 判斷成
#   「門已經在了」⇒ 不起自己的門 ⇒ 進 enclosure 之後 `door_guest` 一路
#   `FileNotFoundError`，agent 拿到 `Cannot connect to API`，
#   而 `agent_pipe_rc` 還是 0。所以這裡改成**真的連一次**。
door_alive() {
  "$PY" - "$DOOR/relay.sock" <<'PYEOF'
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(2)
    s.connect(sys.argv[1]); s.close(); sys.exit(0)
except Exception:
    sys.exit(1)
PYEOF
}

OWNED_DOOR=""
if ! door_alive; then
  echo "門沒有回應 ⇒ 自己起一扇（policy=model）"
  rm -f "$DOOR/relay.sock"
  PYTHONPATH="$REPO" "$PY" -m vacant_network.vrun.proxyd \
      --unix "$DOOR/relay.sock" --path-policy model \
      --state "$BASE/state/relay" \
      --upstream "openai=$UPSTREAM" --upstream "anthropic=$UPSTREAM" \
      > "$OUT/door_relay.log" 2>&1 &
  OWNED_DOOR=$!
  for _ in $(seq 1 250); do door_alive && break; sleep 0.1; done
fi
trap 'if [ -n "$OWNED_DOOR" ]; then kill "$OWNED_DOOR" 2>/dev/null; \
      wait "$OWNED_DOOR" 2>/dev/null; fi' EXIT
door_alive || { echo "門起不來（看 $OUT/door_relay.log），停。"; exit 2; }
echo "門活著（真的連過一次，不是只看檔案在不在）"

# 只讀綁定：node、agent 的安裝目錄、本 kit 的 bin、repo 的 ops（wrap_agent.sh）
RO="$NODE:/home/user1/.local/bin:/home/user1/.local/share/claude"
RO="$RO:/home/user1/.codex/packages:$BIN:$REPO/ops/vacantrun"
[ -d /var/tmp/vacant_hermes ] && RO="$RO:/var/tmp/vacant_hermes"

before=$(wc -l < "$JOURNAL" 2>/dev/null || echo 0); before=${before:-0}
echo "### $AGENT door_calls_before=$before"

ENC_WS="$WS" ENC_RO="$RO" ENC_DOOR="$DOOR" \
ENC_PATH="$NODE/bin:/home/user1/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  "$BIN/enc.sh" /bin/bash "$BIN/inner.sh" "$AGENT" "$WRAP" "$BIN" \
  2>&1 | tee "$OUT/agent_$AGENT.log"
RC=${PIPESTATUS[0]}
after=$(wc -l < "$JOURNAL" 2>/dev/null || echo 0); after=${after:-0}
echo "### $AGENT rc=$RC door_calls_after=$after delta=$((after-before))"

echo "--- 工作區產物 ---"; ls -la "$WS" | head -15
if [ -f "$WS/solution.py" ]; then echo "SOLUTION_PRESENT"; cat "$WS/solution.py";
else echo "SOLUTION_ABSENT"; fi

"$PY" - "$AGENT" "$JOURNAL" "$before" "$RC" "$WS" "$OUT" <<'PYEOF'
import hashlib, json, pathlib, sys
agent, journal, before, rc, ws, out = sys.argv[1:7]
rows = []
p = pathlib.Path(journal)
if p.is_file():
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()][int(before):]
sol = pathlib.Path(ws) / "solution.py"
rec = {"agent": agent, "rc": int(rc),
       "door_calls": len(rows),
       "by_path": {}, "by_status": {},
       "refused_path": sum(1 for r in rows if r.get("refused_path")),
       "solution_present": sol.is_file(),
       "solution_sha256": (hashlib.sha256(sol.read_bytes()).hexdigest()
                           if sol.is_file() else None),
       "solution_text": (sol.read_text(encoding="utf-8", errors="replace")[:400]
                         if sol.is_file() else None)}
for r in rows:
    rec["by_path"][r["path"]] = rec["by_path"].get(r["path"], 0) + 1
    k = str(r.get("status"))
    rec["by_status"][k] = rec["by_status"].get(k, 0) + 1
pathlib.Path(out, f"agent_{agent}.json").write_text(
    json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in rec.items() if k != "solution_text"},
                 ensure_ascii=False))
PYEOF
echo "RUN_AGENT_DONE $AGENT"
