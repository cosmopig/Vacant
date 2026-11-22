#!/usr/bin/env bash
# Ubuntu VM：一次安裝；不啟動付費服務、不執行 agent 題目。
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
STATE=${SANDBOX_STATE:-$HOME/sandbox-rt}
mkdir -p "$STATE" "$HOME/.local/bin"
if ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh -o "$STATE/ollama-install.sh"
  bash "$STATE/ollama-install.sh"
fi
printf '[Service]\nEnvironment="OLLAMA_CONTEXT_LENGTH=32768"\n' > "$STATE/context.conf"
sudo -n mkdir -p /etc/systemd/system/ollama.service.d
if ! cmp -s "$STATE/context.conf" /etc/systemd/system/ollama.service.d/context.conf; then
  sudo -n cp "$STATE/context.conf" /etc/systemd/system/ollama.service.d/context.conf
  sudo -n systemctl daemon-reload
  sudo -n systemctl restart ollama
fi
sudo -n systemctl enable --now ollama
for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:11434/api/version >/dev/null; then break; fi
  sleep 1
done
ollama pull qwen3:8b
export NVM_DIR=${NVM_DIR:-$HOME/.nvm}
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh -o "$STATE/nvm-install.sh"
  bash "$STATE/nvm-install.sh"
fi
# shellcheck disable=SC1091
source "$NVM_DIR/nvm.sh"
nvm install 24
nvm use 24
if npm list -g @mariozechner/pi-coding-agent --depth=0 >/dev/null 2>&1; then
  npm uninstall -g @mariozechner/pi-coding-agent
fi
if [ "$(pi --version 2>/dev/null || true)" != 0.87.1 ]; then
  npm install -g @earendil-works/pi-coding-agent@0.87.1
fi
ln -sfn "$(command -v node)" "$HOME/.local/bin/node"
ln -sfn "$(npm prefix -g)/bin/pi" "$HOME/.local/bin/pi"
AGENT_DIR=${PI_CODING_AGENT_DIR:-$STATE/pi-agent}
mkdir -p "$AGENT_DIR"
python3 - "$HERE/models.json.tmpl" "$AGENT_DIR/models.json" "${RUN_TAG:-smoke}" <<'PY'
import json
from pathlib import Path
import re
import sys
source, destination, tag = sys.argv[1:]
if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', tag):
    raise SystemExit('invalid RUN_TAG')
data = Path(source).read_text().replace('${RUN_TAG}', tag)
json.loads(data)
Path(destination).write_text(data)
PY
printf 'PI_CODING_AGENT_DIR=%s\nProxy: python3 %s/proxy.py --log %s/calls.jsonl\n' "$AGENT_DIR" "$HERE" "$STATE"
