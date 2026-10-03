#!/usr/bin/env bash
# G4／A100 上起 vLLM＋google/gemma-4-12B-it-qat-w4a16-ct（同一組 QAT 權重的 vLLM 原生格式）。log：/content/vllm_setup.log
exec >> /content/vllm_setup.log 2>&1
set -x
date -u
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader
# 獨立 venv：不碰 Colab 預裝的 torch／torchaudio（混用會出現 CUDA 13.0 vs 12.8 的衝突，2026-09-27 實測）
pip install -q uv && uv venv -q -p 3.12 /content/venv-vllm && uv pip install -q -p /content/venv-vllm/bin/python vllm 2>&1 | tail -3
/content/venv-vllm/bin/python -c "import vllm, torch; print('vllm', vllm.__version__, 'torch', torch.__version__, 'cuda', torch.version.cuda)"
curl -fsSL -o /content/tool_chat_template_gemma4.jinja https://raw.githubusercontent.com/vllm-project/vllm/main/examples/tool_chat_template_gemma4.jinja && wc -c /content/tool_chat_template_gemma4.jinja
/content/venv-vllm/bin/hf download google/gemma-4-12B-it-qat-w4a16-ct --local-dir /content/gemma-4-12B-it-qat-w4a16-ct 2>&1 | tail -2
( cd /content/gemma-4-12B-it-qat-w4a16-ct && git ls-remote https://huggingface.co/google/gemma-4-12B-it-qat-w4a16-ct HEAD 2>/dev/null; ls -la; sha256sum *.safetensors ) 
nohup /content/venv-vllm/bin/vllm serve /content/gemma-4-12B-it-qat-w4a16-ct --served-model-name gemma-4-12b-it-qat \
  --max-model-len 262144 --gpu-memory-utilization 0.90 --enable-prefix-caching \
  --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 \
  --chat-template /content/tool_chat_template_gemma4.jinja --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
  --async-scheduling --host 0.0.0.0 --port 18000 > /content/vllm_server.log 2>&1 &
for i in $(seq 1 180); do curl -s localhost:18000/health >/dev/null && break; sleep 5; done
curl -s localhost:18000/v1/models | head -c 300; echo
grep -iE "error|maximum concurrency|KV cache|GPU blocks" /content/vllm_server.log | tail -6
echo VLLM_READY
