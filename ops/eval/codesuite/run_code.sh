#!/bin/bash
# 程式題篩選組的一跑（2026-09-26）：Harbor＋pi（A）或 Harbor＋pi＋使用者的 Vacant 安裝（C*），題目＝`make_lcb_suite.py` 做出來的
# lcb_visible（測試放在工作區、`python3 -m unittest tests/test_public.py`）；模型＝人類自己的機器上的 gemma-4-12b-it-qat，
# 經過記帳代理的本機模式。和 `ops/eval/local/run_local.sh` 同一組旗標（max_turns=15、openai-completions、pi 0.87.1、思考由代理強制關），
# 只差兩處：題目路徑（`CODESUITE`）與 agent 時限——官方 LiveCodeBench 的 360 秒是給雲端模型的，本機一回合就要十幾秒，
# 而 C 組的交件前檢查自己最多 330 秒；不放寬的話時限會系統性地切到 C 組。`--agent-timeout-multiplier 5`＝1800 秒，同 DABstep。
# 用法：run_code.sh <harbor 目錄> <jobs 根目錄> <vacant wheel 或 -> <task_id> <arm：A|C…> <upstream：1003|w401> <sample>
set -uo pipefail
HARBOR_DIR=$1; JOBS=$2; WHEEL=$3; TASK=$4; ARM=$5; UP=$6; SAMPLE=${7:-1}
: "${CODESUITE:?set CODESUITE to the lcb_visible/livecodebench directory}"
CA=/root/.ccr/ca-bundle.crt
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
MODEL=gemma-4-12b-it-qat
AGENT=pi; [ "$ARM" != A ] && AGENT=harbor_vacant:PiWithVacant
TAG="${TAG_PREFIX:-code}-g12-off-$ARM-$TASK-s$SAMPLE"
BASE="http://172.17.0.1:18900/t/$TAG/up/$UP/think/off/api/v1"
OUT="$JOBS/g12-off-$ARM-s$SAMPLE"
mkdir -p "$OUT"
echo "=== $TAG $UP $(date -u +%FT%TZ) ==="
cd "$HARBOR_DIR" || exit 1
PYTHONPATH="$REPO/ops/eval" VACANT_WHEEL="$WHEEL" uv run --no-dev harbor run \
  --path "$CODESUITE" -i "$TASK" \
  --agent "$AGENT" --model "openrouter/$MODEL" \
  --env docker -n 1 -q --job-name "$TAG" --agent-timeout-multiplier 5 \
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
