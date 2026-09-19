#!/usr/bin/env bash
# 一格 ＝ 一次 `vacant run`，**前後各讀一次封包計數器**。
#
#   runcell.sh <cell> <agent> <variant> <task>
#     variant ∈ {wired, half}
#     task    ∈ {deliver, refuse, tool}
#
# 計數器的前後差值就是「這一跑有沒有東西走了中介以外的路」。
# ⚠ 相減期間只有這一格在用 uid 1001 ⇒ 差值才是這一格的（egress_counter 邊界 3）。
set -uo pipefail
R=/var/tmp/vbypass
CELL="$1"; AGENT="$2"; VARIANT="$3"; TASK="${4:-deliver}"
BANK=$R/repo/ops/gain/r535/bank/s1_01_addmul
PORT=${VB_PORT:-18899}
export VB_CELL="$CELL"
export VACANT_RUN_UPSTREAM_OPENAI=${VB_UP_OPENAI:-http://100.86.226.21:1234/v1}
export VACANT_RUN_UPSTREAM_ANTHROPIC=${VB_UP_ANTHROPIC:-http://100.86.226.21:1234}
export VACANT_AGENT_MODEL=${VB_MODEL:-gemma-4-12b-it-qat}

ws=$R/ws/$CELL; rd=$R/rd/$CELL
rm -rf "$ws" "$rd"; mkdir -p "$ws"; chmod 777 "$ws"
case "$TASK" in
  deliver) cp "$BANK/TASK_explicit.md" "$ws/TASK.md" ;;
  refuse)  cp "$BANK/TASK.md"          "$ws/TASK.md" ;;
  tool)    cp "$R/bin/TASK_tool.md"    "$ws/TASK.md" ;;
  *) echo "unknown task: $TASK" >&2; exit 2 ;;
esac
chmod 666 "$ws/TASK.md"

mkdir -p "$R/out/$CELL"
python3 "$R/bin/egress_counter.py" --snapshot --out "$R/out/$CELL/ctr_before.json" >/dev/null
DNS0=$(wc -l < "$R/logs/dns.jsonl" 2>/dev/null || echo 0)

cd "$R/repo" || exit 2
t0=$(date +%s.%N)
# ⚠ `vacant.vrun.launcher` 這個模組名是**刻意不改的**：本輪跑的是
#   `git archive eb655a38` 的樹，那棵樹上套件還叫 `vacant/`。
#   改名（`fb7f4bfb`，vacant → vacant_network，0.8.0）是本輪收工**之後**才落地的。
#   事後改寫這一行等於讓紀錄描述一個沒下過的指令（同 CLAUDE.md 對預註冊逐塊
#   指令的處理）。**要在改名後的樹上重跑，把這一行換成
#   `python3 -m vacant_network.vrun.launcher`，其餘一個字都不用動。**
timeout 900 python3 -m vacant.vrun.launcher \
    --workspace "$ws" --run-dir "$rd" --suite "$BANK/tests_visible" \
    --task-id "vb_$CELL" --sandbox none --port "$PORT" \
    --test-timeout 60 --timeout 600 --retry none --json \
    -- "$R/bin/outer.sh" "$R/bin/inner.sh" "$AGENT" "$VARIANT" \
       "Read TASK.md and do what it says. Use your tools to write the file." \
    > "$R/logs/$CELL.stdout" 2> "$R/logs/$CELL.stderr"
rc=$?
t1=$(date +%s.%N)

python3 "$R/bin/egress_counter.py" --snapshot --out "$R/out/$CELL/ctr_after.json" >/dev/null
python3 "$R/bin/egress_counter.py" \
    --before "$R/out/$CELL/ctr_before.json" --after "$R/out/$CELL/ctr_after.json" \
    --out "$R/out/$CELL/egress_gauge.json" >/dev/null
DNS1=$(wc -l < "$R/logs/dns.jsonl" 2>/dev/null || echo 0)
if [ "$DNS1" -gt "$DNS0" ]; then
  tail -n +$((DNS0 + 1)) "$R/logs/dns.jsonl" | head -n $((DNS1 - DNS0)) \
      > "$R/out/$CELL/dns.jsonl"
else
  : > "$R/out/$CELL/dns.jsonl"
fi

cp "$rd/run_RUN-ON.json"  "$R/out/$CELL/" 2>/dev/null || true
cp "$rd/run_RUN-OFF.json" "$R/out/$CELL/" 2>/dev/null || true
mkdir -p "$R/out/$CELL/wire"
cp "$rd"/wire_RUN-*/index.jsonl "$R/out/$CELL/wire/" 2>/dev/null || true
cp "$R/logs/$CELL.stdout" "$R/out/$CELL/launcher.stdout"
cp "$R/logs/$CELL.stderr" "$R/out/$CELL/launcher.stderr"
awk -v a="$t0" -v b="$t1" -v r="$rc" -v c="$CELL" -v ag="$AGENT" -v v="$VARIANT" -v t="$TASK" \
   'BEGIN{printf "{\"cell\":\"%s\",\"agent\":\"%s\",\"variant\":\"%s\",\"task\":\"%s\",\"launcher_exit\":%d,\"wall_s\":%.2f}\n",c,ag,v,t,r,b-a}' \
   > "$R/out/$CELL/cell.json"
echo "=== $CELL exit=$rc ==="
python3 - "$R/out/$CELL" <<'PY'
import json, pathlib, sys
o = pathlib.Path(sys.argv[1])
r = o / "run_RUN-ON.json"
if r.exists():
    d = json.loads(r.read_text())
    for k in ("accepted", "stop_reason", "requests_seen", "wire_by_protocol",
              "agent_rc", "agent_wall_s", "upstreams_defaulted", "wire_blocked"):
        print(f"  {k:22}= {d.get(k)}")
else:
    print("  <沒有 run_RUN-ON.json——整跑沒有收據>")
g = json.loads((o / "egress_gauge.json").read_text())
print(f"  egress.available      = {g['available']}  reason={g.get('reason')}")
print(f"  off_mediation_packets = {g['off_mediation_packets']}"
      f"  (offbox={g['offbox_packets']} onbox_other={g['onbox_other_packets']}"
      f" mediated={g['mediated_packets']})")
if g.get("v4", {}).get("available"):
    print(f"  v4 = {g['v4']['packets']}")
if g.get("v6", {}).get("available"):
    print(f"  v6 = {g['v6']['packets']}")
names = set()
for ln in (o / "dns.jsonl").read_text().splitlines():
    try: names.add(json.loads(ln)["name"])
    except Exception: pass
print(f"  dns_names ({len(names)}) = {sorted(names)[:14]}")
PY
