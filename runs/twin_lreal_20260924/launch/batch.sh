#!/usr/bin/env bash
# 重錄 L-real：逐項重現 09-19 batch.sh（第一批 3 題 × 3 居民 × 2 題面 = 18 格，四條流），
# 唯一新增：--events（每條流各寫一份 lifecycle，事後依 ts_ms 合併成一份錄影）。
set -uo pipefail
. /var/tmp/vacant_lreal_20260924/env.sh
cd /var/tmp/vacant_lreal_20260924/repo
OUT=/var/tmp/vacant_lreal_20260924/out
WRAP=/var/tmp/vacant_lreal_20260924/repo/ops/vacantrun/wrap_agent.sh
mkdir -p $OUT/lifecycle
echo "===== TWIN LREAL BATCH1 start $(date -u +%FT%TZ) ====="
for k in 0 1 2 3; do
  python3 ops/exhibit/twin/run_twin.py --out $OUT \
    --residents 3 --tasks s1_01_addmul,s1_12_hms,s1_31_money \
    --shard $k:4 \
    --upstream http://100.86.226.21:1234 --model gemma-4-12b-it-qat \
    --evidence L-real --retry revise --max-attempts 3 --timeout 300 \
    --events $OUT/lifecycle/b1_s$k.jsonl \
    -- $WRAP pi "{TASK}" > $OUT.b1stream$k.log 2>&1 &
done
wait
python3 ops/exhibit/twin/run_twin.py --out $OUT --merge-only
echo "===== TWIN LREAL BATCH1 done $(date -u +%FT%TZ) ====="
TASKS=s1_05_initials,s1_24_is_pal,s1_30_ord_suffix,s1_32_pct,s1_34_days_in,s1_49_rgb
echo "===== TWIN LREAL BATCH2 start $(date -u +%FT%TZ) ====="
for k in 0 1 2 3; do
  python3 ops/exhibit/twin/run_twin.py --out $OUT \
    --residents 3 --tasks $TASKS --shard $k:4 \
    --upstream http://100.86.226.21:1234 --model gemma-4-12b-it-qat \
    --evidence L-real --retry revise --max-attempts 3 --timeout 300 \
    --events $OUT/lifecycle/b2_s$k.jsonl \
    -- $WRAP pi "{TASK}" > $OUT.b2stream$k.log 2>&1 &
done
wait
python3 ops/exhibit/twin/run_twin.py --out $OUT --merge-only
echo "===== TWIN LREAL BATCH2 done $(date -u +%FT%TZ) ====="
