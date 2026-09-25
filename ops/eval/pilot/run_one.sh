#!/bin/bash
# 試點／校準的一跑：Harbor＋pi（A）或 Harbor＋pi＋使用者的 Vacant 安裝（C），真模型經過記帳代理。
# 用法：run_one.sh <harbor 目錄> <jobs 根目錄> <vacant wheel> <task_id> <q38|g4> <on|off> <A|C> [base_url]
# 題目：釘死的本機資料集（DABSTEP_PINNED，`ops/eval/dabstep_pin.py` 產生；所有題目、條件同一個映像）。
# base_url 省略＝記帳代理（真模型）；閘門測試時給假模型的網址。
# 和閘門 1 同一組旗標（--ak max_turns=15 model_api=openai-completions version=0.87.1）；思考開關由代理依網址強制；
# 每一跑一個標籤（代理對每個標籤有 0.30 美元上限）；不設任何 Vacant 環境變數。
set -uo pipefail
HARBOR_DIR=$1; JOBS=$2; WHEEL=$3; TASK=$4; M=$5; THINK=$6; ARM=$7; BASE=${8:-}
: "${DABSTEP_PINNED:?set DABSTEP_PINNED to the pinned dataset directory}"
CA=/root/.ccr/ca-bundle.crt
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
case $M in
  q38) MODEL=qwen/qwen3.8-27b ;;
  g4)  MODEL=google/gemma-4-26b-a4b-it ;;
  *) echo "unknown model $M"; exit 2 ;;
esac
AGENT=pi; [ "$ARM" = C ] && AGENT=harbor_vacant:PiWithVacant
TAG="pilot-$M-$THINK-$ARM-$TASK${RUN_SUFFIX:+-$RUN_SUFFIX}"   # 重跑用 RUN_SUFFIX 分開記帳
[ -n "$BASE" ] || BASE="http://172.17.0.1:18900/t/$TAG/think/$THINK/api/v1"
KEY=sk-dummy; case $BASE in *18900*) ;; *) KEY=sk-fake-gate ;; esac
OUT="$JOBS/$M-$THINK-$ARM"
mkdir -p "$OUT"
echo "=== $TAG $(date -u +%FT%TZ) ==="
cd "$HARBOR_DIR" || exit 1
PYTHONPATH="$REPO/ops/eval" VACANT_WHEEL="$WHEEL" uv run --no-dev harbor run \
  --path "$DABSTEP_PINNED" -i "dabstep-$TASK" \
  --agent "$AGENT" --model "openrouter/$MODEL" \
  --env docker -n 1 -q \
  --mounts "[{\"type\":\"bind\",\"source\":\"$CA\",\"target\":\"/usr/local/share/ccr-ca-bundle.crt\",\"read_only\":true}]" \
  --ae OPENROUTER_API_KEY=$KEY \
  --ae "OPENROUTER_BASE_URL=$BASE" \
  --ae SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ae CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ae NODE_EXTRA_CA_CERTS=/usr/local/share/ccr-ca-bundle.crt \
  --ve SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ve CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1 \
  --jobs-dir "$OUT"
echo "=== exit $? $(date -u +%FT%TZ) ==="
