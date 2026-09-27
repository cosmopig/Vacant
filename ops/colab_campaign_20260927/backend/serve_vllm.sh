#!/usr/bin/env bash
# 只起服務（venv 與模型已就位）。log：/content/vllm_serve.log、/content/vllm_server.log
exec >> /content/vllm_serve.log 2>&1
set -x
M=/content/gemma-4-12B-it-qat-w4a16-ct
/content/venv-vllm/bin/python -c "import vllm, torch; print('vllm', vllm.__version__, 'torch', torch.__version__, 'cuda', torch.version.cuda)"
curl -s https://huggingface.co/api/models/google/gemma-4-12B-it-qat-w4a16-ct | /content/venv-vllm/bin/python -c "import json,sys; d=json.load(sys.stdin); print('HF_SHA', d.get('sha'), 'lastModified', d.get('lastModified'))"
sha256sum $M/model.safetensors $M/chat_template.jinja /content/tool_chat_template_gemma4.jinja
# FlashInfer 的 top-k/top-p 採樣器在 sm_120（RTX PRO 6000）上誤判成「低於 sm75」而崩（vLLM 0.30.0／flashinfer 0.6.18，2026-09-27）⇒ 改用原生採樣器
VLLM_USE_FLASHINFER_SAMPLER=0 nohup /content/venv-vllm/bin/vllm serve $M --served-model-name gemma-4-12b-it-qat \
  --max-model-len 262144 --gpu-memory-utilization 0.90 --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 \
  --chat-template /content/tool_chat_template_gemma4.jinja --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
  --async-scheduling --host 0.0.0.0 --port 18000 > /content/vllm_server.log 2>&1 &
for i in $(seq 1 240); do curl -s localhost:18000/health >/dev/null && break; sleep 5; done
curl -s localhost:18000/v1/models | head -c 200; echo
grep -iE "maximum concurrency|KV cache|GPU KV" /content/vllm_server.log | tail -4
echo VLLM_READY
