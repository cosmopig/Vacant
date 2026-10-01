#!/usr/bin/env bash
# VM（root）：把 vLLM 0.30.0 ＋ google/gemma-4-12B-it-qat-w4a16-ct 架起來（獨立 venv、port 18000、只聽 127.0.0.1），可重跑（冪等）。
# 用法：setsid nohup bash vllm_up_i1001.sh > /dev/null 2>&1 < /dev/null &      # log：/content/vllm_up.log；最後一行 VLLM_READY（或 VLLM_FAIL <原因>）
#       bash vllm_up_i1001.sh --dry-run                                         # 只印會用的 serve 指令與要核對的雜湊，不裝、不下載、不起服務
#
# 這支在架構裡承重什麼：預註冊的固定變數（模型權重、聊天樣板、vLLM 版本、serve 旗標）是在 VM 上才成立的；
# 第一批把安裝（setup_vllm.sh）與服務（serve_vllm.sh）拆成兩支，而 setup_vllm.sh 結尾那條 serve 是**舊的、會崩的**（沒關 FlashInfer 採樣器、
# 沒開 --enable-prompt-tokens-details、聽 0.0.0.0）。這裡把「安裝（setup_vllm.sh 前半）」與「serve_vllm.sh 的旗標」合成一支，
# 旗標逐字取自 serve_vllm.sh（2026-09-27 G4 上實際跑完 1,840 格的那一條），再加三道核對：版本釘 0.30.0、權重 sha256、聊天樣板 sha256 前綴。
# 來源：origin/feat/colab-campaign-20260927 的 ops/colab_campaign_20260927/backend/{setup_vllm.sh,serve_vllm.sh}（本分支沒有）。
# 誠實邊界：**這支沒有在 Colab 上跑過、這個容器沒有 GPU 也沒有 vLLM**；本機只驗了語法與 --dry-run 的輸出（tests/test_colab_i1001_ops.py）。
# Colab 條款禁止對外的網頁服務與遠端代理 ⇒ 只聽 127.0.0.1（改成 0.0.0.0 等於違規，測試會擋）。
set -euo pipefail
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
VLLM_VERSION=${VLLM_VERSION:-0.30.0}
MODEL_ID=google/gemma-4-12B-it-qat-w4a16-ct
M=/content/gemma-4-12B-it-qat-w4a16-ct
V=/content/venv-vllm
TPL=/content/tool_chat_template_gemma4.jinja
# 預註冊（PREREG_20261001_COLAB_INTERACTIVE_I1001.md 第四節）釘的雜湊；樣板與 chat_template 只有前綴是已知的（C5 預註冊只記了前綴）
MODEL_SHA=60b6e3989502969d8ae04185d72ecbbc7db63978d5af747a493d53895aa6bfa3
TPL_SHA_PREFIX=afdbb2ab
CHAT_SHA_PREFIX=ae53464b
PORT=18000
SERVE_ARGS=(--served-model-name gemma-4-12b-it-qat --max-model-len 262144 --gpu-memory-utilization 0.90 --enable-prefix-caching
  --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 --chat-template "$TPL"
  --limit-mm-per-prompt '{"image": 0, "audio": 0}' --async-scheduling --enable-prompt-tokens-details --host 127.0.0.1 --port "$PORT")

if [ "$DRY" = 1 ]; then
  echo "VLLM_VERSION=${VLLM_VERSION}"
  echo "MODEL_SHA=${MODEL_SHA}"
  echo "TPL_SHA_PREFIX=${TPL_SHA_PREFIX} CHAT_SHA_PREFIX=${CHAT_SHA_PREFIX}"
  echo "VLLM_USE_FLASHINFER_SAMPLER=0 ${V}/bin/vllm serve ${M} ${SERVE_ARGS[*]}"
  exit 0
fi

exec >> /content/vllm_up.log 2>&1
fail() { echo "VLLM_FAIL $*"; exit 3; }
date -u +%FT%TZ
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader || fail "nvidia-smi"

# 1) 獨立 venv（不碰 Colab 預裝的 torch／torchaudio：混用會有 CUDA 13.0 vs 12.8 的衝突，2026-09-27 實測）
if [ ! -x "${V}/bin/vllm" ]; then
  pip install -q uv
  uv venv -q -p 3.12 "$V"
  uv pip install -q -p "${V}/bin/python" "vllm==${VLLM_VERSION}"
fi
GOT=$("${V}/bin/python" -c 'import vllm; print(vllm.__version__)')
[ "$GOT" = "$VLLM_VERSION" ] || fail "vllm 版本 ${GOT} != ${VLLM_VERSION}"
"${V}/bin/python" -c 'import vllm, torch; print("vllm", vllm.__version__, "torch", torch.__version__, "cuda", torch.version.cuda)'

# 2) 工具呼叫樣板（第一批從 main 取；先試 main，雜湊前綴不符再試 v${VLLM_VERSION} 標籤，都不符就停——樣板是固定變數）
if [ ! -s "$TPL" ] || ! sha256sum "$TPL" | grep -q "^${TPL_SHA_PREFIX}"; then
  for ref in main "v${VLLM_VERSION}"; do
    curl -fsSL -o "$TPL" "https://raw.githubusercontent.com/vllm-project/vllm/${ref}/examples/tool_chat_template_gemma4.jinja" || continue
    sha256sum "$TPL" | grep -q "^${TPL_SHA_PREFIX}" && break
  done
fi
sha256sum "$TPL"
sha256sum "$TPL" | grep -q "^${TPL_SHA_PREFIX}" || fail "tool_chat_template_gemma4.jinja 的 sha256 前綴不是 ${TPL_SHA_PREFIX}（固定變數對不上；要換就是另一份預註冊）"

# 3) 權重
if [ ! -s "${M}/model.safetensors" ]; then
  "${V}/bin/hf" download "$MODEL_ID" --local-dir "$M" 2>&1 | tail -2
fi
( cd "$M" && ls -la && sha256sum model.safetensors chat_template.jinja )
( cd "$M" && sha256sum model.safetensors | grep -q "^${MODEL_SHA}" ) || fail "model.safetensors 的 sha256 不是 ${MODEL_SHA}"
( cd "$M" && sha256sum chat_template.jinja | grep -q "^${CHAT_SHA_PREFIX}" ) || fail "chat_template.jinja 的 sha256 前綴不是 ${CHAT_SHA_PREFIX}"

# 4) serve（FlashInfer 的 top-k/top-p 採樣器在 sm_120 誤判成「低於 sm75」而崩，vLLM 0.30.0／flashinfer 0.6.18 ⇒ 用原生採樣器）
if ! curl -s -o /dev/null "http://127.0.0.1:${PORT}/health"; then
  VLLM_USE_FLASHINFER_SAMPLER=0 setsid nohup "${V}/bin/vllm" serve "$M" "${SERVE_ARGS[@]}" > /content/vllm_server.log 2>&1 < /dev/null &
fi
for _ in $(seq 1 360); do curl -s -o /dev/null "http://127.0.0.1:${PORT}/health" && break; sleep 5; done
curl -s -o /dev/null "http://127.0.0.1:${PORT}/health" || fail "serve 30 分鐘內沒有起來（看 /content/vllm_server.log）"
curl -s "http://127.0.0.1:${PORT}/v1/models" | head -c 300; echo
grep -iE "maximum concurrency|KV cache|GPU KV" /content/vllm_server.log | tail -4 || true
date -u +%FT%TZ
echo VLLM_READY
