#!/usr/bin/env bash
# R532 發射驅動（DECISION_20260917_R532_STRONGER_MODEL_PREREG.md §二-5）
#
# 這支在架構裡承重什麼：本輪**不使用 `schedule_queue.py`**（其 QUEUE_SLOTS／PER_HOST_CAP=4
# 是 R529 的凍結碼，改它會動到別的實驗），改為直接發 runner。每台後端同時只跑一塊，
# 一塊收完才發下一塊；1003 與 1004 各自一條序列、互不等待。
#
# 用法：run_r532_queue.sh <host_label> <endpoint>
#   例：run_r532_queue.sh 1003 http://100.119.113.56:1234/v1
# 塊的分配由 R532_HOSTS 檔決定（每行 "<host_label> <block_name>"），由 plan_r532.py 產生。
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 1

HOST_LABEL="$1"; ENDPOINT="$2"
# 端點走 **`VACANT_GAIN_API`**，不是 `VACANT_ENDPOINT`——後者只管 substrate.py，
# `brain_cline.py:134` 讀的是 `VACANT_GAIN_API`，沒設就打 `api.cline.bot` 雲端
# （2026-09-17 誤發兩次才發現，產物留在 runs/_falsestart_20260917_*）。
# 值要與 12B 那輪逐字相同：`http://<host>:1234/v1/chat/completions`。
case "$ENDPOINT" in
  */v1/chat/completions) ;;
  *) echo "ENDPOINT 必須是完整的 /v1/chat/completions（與 R529 逐字相同）" >&2; exit 2;;
esac
PLAN="ops/gain/r532/plan_${HOST_LABEL}.txt"
QUEUE="ops/gain/queues/r532.json"
DEC="DECISION_20260917_R532_STRONGER_MODEL_PREREG.md"
LOGDIR="$HOME/vacant/logs"; mkdir -p "$LOGDIR"
DRIVER_LOG="$LOGDIR/r532_driver_${HOST_LABEL}.log"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$DRIVER_LOG"; }

# 單一驅動鎖：同一台不准有兩條序列（重複發射過一次，見 R530 附錄 A-17）
exec 9>"/tmp/r532_driver_${HOST_LABEL}.lock"
flock -n 9 || { log "另一條驅動已在跑，退出"; exit 0; }

log "=== 驅動啟動 host=$HOST_LABEL endpoint=$ENDPOINT plan=$PLAN"
log "repo HEAD=$(git rev-parse --short HEAD) prereg_sha=$(sha256sum $DEC | cut -c1-16)"

while read -r BLOCK; do
  [ -z "$BLOCK" ] && continue
  OUT="runs/$BLOCK"
  if [ -f "$OUT/summary.json" ]; then log "$BLOCK 已有 summary.json，跳過"; continue; fi

  # 逐塊參數一律從佇列 JSON 取，不在這支腳本裡重寫（避免兩份真相）
  eval "$(python3 - "$QUEUE" "$BLOCK" <<'PY'
import json,sys,shlex
q=json.load(open(sys.argv[1])); bl=q["blocks"] if isinstance(q,dict) else q
b=[x for x in bl if x["name"]==sys.argv[2]]
if len(b)!=1: print("BAD=1"); sys.exit()
b=b[0]
print("N=%s" % b["n"]); print("OFFSET=%s" % b["offset"])
print("SEED=%s" % shlex.quote(b["seed"])); print("BANK=%s" % shlex.quote(b["bank"]))
print("BFILTER=%s" % shlex.quote(b.get("bank_filter","")))
print("BAD=0")
PY
)"
  [ "${BAD:-1}" = "0" ] || { log "$BLOCK 在佇列裡找不到或重複，停"; exit 1; }

  FILTER_ARG=()
  [ -n "$BFILTER" ] && FILTER_ARG=(--bank-filter "$BFILTER")

  log "→ 發 $BLOCK  n=$N offset=$OFFSET seed=$SEED bank=$BANK ${BFILTER:+filter=$BFILTER}"
  VACANT_GAIN_API="$ENDPOINT" \
  setsid python3 ops/gain/gain_run.py \
    --out "$OUT" --n "$N" --offset "$OFFSET" \
    --decision "$DEC" \
    --seed "$SEED" --arms OFF,CONFORM,HMIX \
    --bank "$BANK" "${FILTER_ARG[@]}" \
    --record-bank-field --models qwen3-27b \
    --reasoning-effort none \
    --probe-sample 0 --gauge-scope bank \
    --request-timeout-s 900 --review-timeout-s 380 --retries 4 \
    >> "$LOGDIR/${BLOCK}.log" 2>&1
  RC=$?
  if [ -f "$OUT/summary.json" ]; then
    log "✓ $BLOCK 收完 rc=$RC"
  else
    log "✗ $BLOCK rc=$RC 沒有 summary.json——停下這條序列（不自動重試，留給稽核）"
    exit 1
  fi
done < "$PLAN"
log "=== $HOST_LABEL 序列全部收完"
