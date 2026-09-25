#!/bin/bash
# Gate 1 single-run driver. Usage:
#   run_one.sh <dataset@version> <task-name> <model-id> <tag> <jobs-subdir>
set -uo pipefail
HARBOR_DIR=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/study/src/harbor
JOBS_ROOT=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/evalrun/gate1/jobs
CA=/root/.ccr/ca-bundle.crt

DATASET="$1"
TASK="$2"
MODEL="$3"
TAG="$4"
SUBDIR="$5"

JOBS_DIR="$JOBS_ROOT/$SUBDIR"
mkdir -p "$JOBS_DIR"

cd "$HARBOR_DIR" || exit 1

echo "=== RUN $TAG === dataset=$DATASET task=$TASK model=$MODEL ==="
date -u

uv run --no-dev harbor run \
  --dataset "$DATASET" \
  -i "$TASK" \
  --agent pi \
  --model "openrouter/$MODEL" \
  --env docker -n 1 -q \
  --mounts "[{\"type\":\"bind\",\"source\":\"$CA\",\"target\":\"/usr/local/share/ccr-ca-bundle.crt\",\"read_only\":true}]" \
  --ae OPENROUTER_API_KEY=sk-dummy \
  --ae "OPENROUTER_BASE_URL=http://172.17.0.1:18900/t/$TAG/api/v1" \
  --ae SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ae CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ae NODE_EXTRA_CA_CERTS=/usr/local/share/ccr-ca-bundle.crt \
  --ve SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ve CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1 \
  --jobs-dir "$JOBS_DIR"

echo "=== exit code: $? ==="
date -u
