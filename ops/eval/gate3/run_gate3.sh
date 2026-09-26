#!/bin/bash
# 閘門 3（零設定 v3，L-fake，不花錢）：Harbor＋pi 0.87.1＋回合上限，假模型照劇本一直查、從來不寫答案檔
# （付費批次 55 個「沒交」的樣子）；看到 v3 的回合預算提醒之後才寫。A、C1（現版）、C2（v3）各一跑。
# 預期：A＝0、C1＝0（上限切斷、交件前檢查輪不到）、C2＝1（第 N-2 回合之後提醒 → 寫檔）。
# 用法：run_gate3.sh <harbor 目錄> <jobs 根目錄> <釘死的題目目錄> <C1 wheel> <C2 wheel> [max_turns]
set -uo pipefail
HARBOR_DIR=$1; JOBS=$2; DATA=$3; W1=$4; W2=$5; MAXT=${6:-15}
CA=/root/.ccr/ca-bundle.crt
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
SCN=$REPO/ops/eval/gate3/scenario_capped.json
PORT=18082
mkdir -p "$JOBS"
MOCK_HOST=172.17.0.1 MOCK_SCENARIO=$SCN MOCK_LOG=$JOBS/mock.jsonl \
  python3 "$REPO/ops/intake/mock_model.py" $PORT > "$JOBS/mock.out" 2>&1 &
MOCK=$!
trap 'kill $MOCK 2>/dev/null' EXIT
sleep 1
for ARM in A C1 C2; do
  AGENT=pi; W=-; [ "$ARM" = C1 ] && { AGENT=harbor_vacant:PiWithVacant; W=$W1; }
  [ "$ARM" = C2 ] && { AGENT=harbor_vacant:PiWithVacant; W=$W2; }
  mkdir -p "$JOBS/$ARM"
  ( cd "$HARBOR_DIR" && PYTHONPATH="$REPO/ops/eval" VACANT_WHEEL="$W" uv run --no-dev harbor run \
    --path "$DATA" -i dabstep-5 --job-name "gate3-$ARM" \
    --agent "$AGENT" --model "openrouter/mock-model" \
    --env docker -n 1 -q \
    --mounts "[{\"type\":\"bind\",\"source\":\"$CA\",\"target\":\"/usr/local/share/ccr-ca-bundle.crt\",\"read_only\":true}]" \
    --ae OPENROUTER_API_KEY=sk-fake-gate3 \
    --ae "OPENROUTER_BASE_URL=http://172.17.0.1:$PORT/v1" \
    --ae SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
    --ae CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
    --ae NODE_EXTRA_CA_CERTS=/usr/local/share/ccr-ca-bundle.crt \
    --ve SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
    --ve CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
    --ak max_turns=$MAXT --ak model_api=openai-completions --ak version=0.87.1 \
    --jobs-dir "$JOBS/$ARM" ) > "$JOBS/$ARM.log" 2>&1
  echo "$ARM exit=$? reward=$(cat $JOBS/$ARM/gate3-$ARM/*/verifier/reward.txt 2>/dev/null)"
done
