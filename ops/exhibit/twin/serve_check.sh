#!/bin/bash
# `twinlink serve` 的唯讀驗收＋負控制。
WT=/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/agent-adaefe3b88900fcee
PY=/Users/cosmopig/Documents/GitHub/Vacant/.venv/bin/python
OUT="$WT/ops/exhibit/twin/evidence_serve_20260920"
DB="$OUT/serve.sqlite3"
PORT=8907
rm -rf "$OUT"; mkdir -p "$OUT"

if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "拒絕啟動：埠 $PORT 有人在聽"; exit 2
fi

# 先塞兩筆真資料進去
"$PY" "$WT/ops/exhibit/twin/twinstore.py" --db "$DB" note "serve 驗收用" >/dev/null
"$PY" - <<PY
import sys; sys.path.insert(0, "$WT")
from ops.exhibit.twin.twinstore import TwinStore, KIND_SUBMITTED, KIND_GENERATED
s = TwinStore("$DB")
s.append(KIND_SUBMITTED, "v1", {"card": {"need": "排書"}}, source="check")
s.append(KIND_GENERATED, "v1", {"arrival":"嗨","working":"做","handover":"好了",
                                "engine":"fallback_deterministic"}, source="check")
s.close()
PY

BEFORE=$(shasum -a 256 "$DB" | cut -d' ' -f1)
echo "開服前 DB sha256 = $BEFORE" | tee "$OUT/01_before.txt"

"$PY" "$WT/ops/exhibit/twin/twinlink.py" --db "$DB" serve --port $PORT > "$OUT/02_serve.log" 2>&1 &
SP=$!
trap 'kill $SP 2>/dev/null; wait $SP 2>/dev/null' EXIT
sleep 2

echo
echo "=== 三個端點都要回 200 ==="
for p in /visitors.json /verify /stats; do
  printf '  %-16s HTTP ' "$p"
  n=$(echo "${p#/}" | tr -d './')
  curl -sS -o "$OUT/03_$n.json" -w '%{http_code}\n' --max-time 10 "http://127.0.0.1:$PORT$p"
done
echo "  不存在的路徑 → HTTP $(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:$PORT/nope)  （應該 404）"

echo
echo "=== 內容 ==="
cat "$OUT/03_verify.json"; echo
cat "$OUT/03_stats.json"; echo

echo "=== 🔴 唯讀負控制：打了 30 次之後 DB 一個 byte 都不准變 ==="
for i in $(seq 1 30); do curl -sS -o /dev/null --max-time 10 "http://127.0.0.1:$PORT/visitors.json"; done
AFTER=$(shasum -a 256 "$DB" | cut -d' ' -f1)
echo "開服後 DB sha256 = $AFTER" | tee -a "$OUT/01_before.txt"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "  [OK] DB 沒被動過（唯讀是真的）"
else
  echo "  [紅] DB 變了！唯讀是假的"
  exit 1
fi

echo
echo "=== 對照組：可寫模式寫一筆，sha256 必須變（證明剛剛的相同不是量具壞了）==="
"$PY" "$WT/ops/exhibit/twin/twinstore.py" --db "$DB" note "對照組" >/dev/null
CTRL=$(shasum -a 256 "$DB" | cut -d' ' -f1)
echo "寫入後 sha256 = $CTRL"
if [ "$AFTER" != "$CTRL" ]; then
  echo "  [OK] 寫得進去時 sha256 確實會變 ⇒ 上面那個「沒變」有意義"
else
  echo "  [紅] 連寫入都沒讓 sha256 變，量具壞了"
  exit 1
fi
echo
echo "serve 驗收全綠"
