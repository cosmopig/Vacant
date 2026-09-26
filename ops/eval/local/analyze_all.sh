#!/bin/bash
# 兩個本機批次跑完之後的分析（照兩份預註冊第五／六節；2026-09-26）。每一步都只讀 jobs 目錄與代理的紀錄。
#   正式批次：analyze_local（主要 C2:A；次要 C1:A、C2:C1，Holm）＋ split_ended（事後、描述）＋ 牆鐘逾時每組幾跑
#   留出批次：analyze_local（主要 C3:A）＋ reminder_writes（提醒之後才寫的答案有沒有出處）＋ 牆鐘逾時每組幾跑
# 用法：analyze_all.sh <formal|heldout> <local 暫存根目錄> <釘死的題目根目錄> <輸出目錄>
set -euo pipefail
WHICH=$1; L=$2; PIN=$3; OUT=$4
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
PY=$REPO/.venv/bin/python
mkdir -p "$OUT"
cd "$REPO"
if [ "$WHICH" = formal ]; then
  JOBS=$L/formal_v3; DATA=$PIN/formal; PREFIX=v3local; ARMS="A C1 C2"
  "$PY" ops/eval/local/analyze_local.py --jobs "$JOBS" --ledger "$L/ledger" --dataset "$DATA" --prefix "$PREFIX" \
    --out "$OUT" --primary C2:A --secondary C1:A C2:C1 --io "$L/ledger/io.jsonl"
  python3 ops/eval/local/split_ended.py --jobs "$JOBS" --arm C2 --out "$OUT/split_ended_C2.json" > /dev/null
else
  JOBS=$L/heldout_v34; DATA=$PIN/dabstep; PREFIX=h34; ARMS="A C3"
  "$PY" ops/eval/local/analyze_local.py --jobs "$JOBS" --ledger "$L/ledger" --dataset "$DATA" --prefix "$PREFIX" \
    --out "$OUT" --primary C3:A --io "$L/ledger/io.jsonl"
  python3 ops/eval/local/reminder_writes.py --jobs "$JOBS" --arm C3 --out "$OUT/reminder_writes_C3.json" > /dev/null
  python3 ops/eval/local/split_ended.py --jobs "$JOBS" --arm C3 --out "$OUT/split_ended_C3.json" > /dev/null
fi
# Harbor 的牆鐘時限（AgentTimeoutError）與其他例外，每組每一次幾跑（描述）
python3 - "$OUT/cells.json" "$OUT/exceptions.json" <<'EOF'
import collections, json, sys
rows = json.load(open(sys.argv[1]))
rows = rows.get("cells", rows) if isinstance(rows, dict) else rows
c = collections.Counter((r["arm"], r["sample"], r.get("exception") or "none") for r in rows)
out = [{"arm": a, "sample": s, "exception": e, "runs": n} for (a, s, e), n in sorted(c.items())]
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(json.dumps([o for o in out if o["exception"] != "none"], indent=1))
EOF
ls "$OUT"
