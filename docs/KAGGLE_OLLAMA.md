# Kaggle notebook: Ollama tunnel for the personal pilot

This is the notebook setup for a live Twin-2K-500 run against Ollama on Kaggle. The personal backend reads `ops/personal_pilot/config.kaggle.example.json`. Replace the placeholder tunnel host before calling the model. The default model is `qwen3.8:27b`; set `VACANT_MODEL` to `gemma4:12b` for the other run. Both need `reasoning_effort: none` on `/v1/chat/completions`. `think: false` is not sent: that flag is ignored on the OpenAI-compatible route, and `max_tokens` alone leaves `content` empty because the tokens go to reasoning.

## Install zstd before the Ollama installer

The Ollama install script unpacks with zstd. Install it first.

```python
import subprocess
subprocess.check_call(["apt-get", "update"])
subprocess.check_call(["apt-get", "install", "-y", "zstd", "curl"])
subprocess.check_call("curl -fsSL https://ollama.com/install.sh | sh", shell=True)
```

## Start the servers so a keep-alive cell can be interrupted

Start Ollama, the proxy, and cloudflared in a new session. Do not call `terminate()` or `kill()` in a `finally` on the cell that only keeps the notebook alive. Interrupting that cell must leave the servers running.

```python
import os
import subprocess
from pathlib import Path

log_dir = Path("/tmp/vacant-kaggle")
log_dir.mkdir(exist_ok=True)

def start_detached(cmd):
    log = open(log_dir / (cmd[0].replace("/", "_") + ".log"), "ab")
    return subprocess.Popen(
        cmd,
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"
ollama = start_detached(["ollama", "serve"])
# pull the model you will point VACANT_MODEL at
subprocess.check_call(["ollama", "pull", os.environ.get("VACANT_MODEL", "qwen3.8:27b")])
# proxy and cloudflared are started the same way: start_new_session=True, no terminate in finally
proxy = start_detached(["python3", "your_proxy.py"])
tunnel = start_detached(["cloudflared", "tunnel", "--url", "http://127.0.0.1:11434"])
print("pids", ollama.pid, proxy.pid, tunnel.pid)
```

The keep-alive cell is only a sleep loop. It has no `finally` that stops those processes.

```python
import time
while True:
    time.sleep(60)
```

## Point the pilot at the tunnel

```bash
export VACANT_PERSONAL_API_KEY=ollama
export VACANT_MODEL=qwen3.8:27b   # or gemma4:12b
python3 -m vacant_network.personal twin2k-run \
  --config ops/personal_pilot/config.kaggle.example.json \
  --prepared "$HOME/vacant-twin2k-20" \
  --backend openai \
  --out "$HOME/vacant-twin2k-${VACANT_MODEL}"
```

If the tunnel drops, run the same command again with `--resume`. Completed `(pid, arm, case_id)` rows are skipped. A row whose status is `usage_unknown` is left in place and not resent, so a request that may already have been billed is not counted twice. Timeout and connection errors are retried once inside the twin run and do not stop the remaining cells.
