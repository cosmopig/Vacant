#!/bin/bash
# 本機算力的一跑（2026-09-26）：Harbor＋pi（A）或 Harbor＋pi＋使用者的 Vacant 安裝（C*），
# 模型＝人類自己的兩台機器上的 gemma-4-12b-it-qat（LM Studio），經過記帳代理的本機模式（`ops/eval/orproxy.py` 的 upstreams）。
# 用法：run_local.sh <harbor 目錄> <jobs 根目錄> <vacant wheel 或 -> <task_id> <arm：A|C1|C2…> <upstream：1003|w401> <sample>
# 和付費批次同一組旗標（max_turns=15、model_api=openai-completions、pi 0.87.1）；思考由代理強制關（兩台都做得到的設定）。
# C* 的差別只在 wheel（哪一版 Vacant）；不設任何 Vacant 環境變數。每一跑一個 job 名（避免同一秒撞目錄）。
set -uo pipefail
HARBOR_DIR=$1; JOBS=$2; WHEEL=$3; TASK=$4; ARM=$5; UP=$6; SAMPLE=${7:-1}
: "${DABSTEP_PINNED:?set DABSTEP_PINNED to the pinned dataset directory}"
CA=/root/.ccr/ca-bundle.crt
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
MODEL=gemma-4-12b-it-qat
AGENT=pi; [ "$ARM" != A ] && AGENT=harbor_vacant:PiWithVacant
TAG="${TAG_PREFIX:-local}-g12-off-$ARM-$TASK-s$SAMPLE"
BASE="http://172.17.0.1:18900/t/$TAG/up/$UP/think/off/api/v1"
OUT="$JOBS/g12-off-$ARM-s$SAMPLE"
mkdir -p "$OUT"
echo "=== $TAG $UP $(date -u +%FT%TZ) ==="
cd "$HARBOR_DIR" || exit 1
PYTHONPATH="$REPO/ops/eval" VACANT_WHEEL="$WHEEL" uv run --no-dev harbor run \
  --path "$DABSTEP_PINNED" -i "dabstep-$TASK" \
  --agent "$AGENT" --model "openrouter/$MODEL" \
  --env docker -n 1 -q --job-name "$TAG" \
  --mounts "[{\"type\":\"bind\",\"source\":\"$CA\",\"target\":\"/usr/local/share/ccr-ca-bundle.crt\",\"read_only\":true}]" \
  --ae OPENROUTER_API_KEY=sk-dummy \
  --ae "OPENROUTER_BASE_URL=$BASE" \
  --ae SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ae CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ae NODE_EXTRA_CA_CERTS=/usr/local/share/ccr-ca-bundle.crt \
  --ve SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ve CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1 \
  --jobs-dir "$OUT"
echo "=== exit $? $(date -u +%FT%TZ) ==="
