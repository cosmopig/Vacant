#!/bin/bash
# 閘門 2：在 Harbor 裡（和正式評測同一個框架、同一個題目、同一組旗標）用照劇本的假模型跑 A 與 C，
# 證明 C 組的包裝真的把 Vacant 裝上、交件前檢查真的跑、退回真的送到模型、答案檔真的改了。不花錢。
# 用法：run_gate2.sh <harbor 目錄> <jobs 根目錄> <vacant wheel> <劇本 JSON>
set -uo pipefail
HARBOR_DIR=$1; JOBS=$2; WHEEL=$3; SCN=$4
CA=/root/.ccr/ca-bundle.crt
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
PORT=18081
MOCK_HOST=172.17.0.1 MOCK_SCENARIO=$SCN MOCK_LOG=$JOBS/mock.jsonl \
  python3 "$REPO/ops/intake/mock_model.py" $PORT > "$JOBS/mock.out" 2>&1 &
MOCK=$!
trap 'kill $MOCK 2>/dev/null' EXIT
sleep 1
for ARM in A C; do
  AGENT=pi; [ "$ARM" = C ] && AGENT=harbor_vacant:PiWithVacant
  mkdir -p "$JOBS/$ARM"
  ( cd "$HARBOR_DIR" && PYTHONPATH="$REPO/ops/eval" VACANT_WHEEL="$WHEEL" uv run --no-dev harbor run \
    --dataset "dabstep@1.0" -i dabstep-5 \
    --agent "$AGENT" --model "openrouter/mock-model" \
    --env docker -n 1 -q \
    --mounts "[{\"type\":\"bind\",\"source\":\"$CA\",\"target\":\"/usr/local/share/ccr-ca-bundle.crt\",\"read_only\":true}]" \
    --ae OPENROUTER_API_KEY=sk-fake-gate2 \
    --ae "OPENROUTER_BASE_URL=http://172.17.0.1:$PORT/v1" \
    --ae SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
    --ae CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
    --ae NODE_EXTRA_CA_CERTS=/usr/local/share/ccr-ca-bundle.crt \
    --ve SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
    --ve CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
    --ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1 \
    --jobs-dir "$JOBS/$ARM" ) > "$JOBS/$ARM.log" 2>&1
  echo "$ARM exit=$?"
done
