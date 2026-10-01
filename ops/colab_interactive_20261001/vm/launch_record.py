#!/usr/bin/env python3
"""launch_record — 發射紀錄：把這一批用到的每樣東西的 sha256 與版本釘進 `/srv/eval/env_manifest.json`（packer 會打進 chunk）
和 `/srv/eval/launch_record_<前綴>.json`。對照第一批 launch_batch.sh 的內嵌 python，另加：tmux／bwrap 版本、bridge 檔、
selfcheck 摘要（含 bridge 墊片有沒有用）、題庫索引與 MANIFEST 的 sha256。

    python3 launch_record.py <前綴> <位置數> <時限 UTC> <鏡像目錄>
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time


def h(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(d: pathlib.Path) -> str:
    m = hashlib.sha256()
    for f in sorted(d.rglob("*")):
        if f.is_file():
            m.update(str(f.relative_to(d)).encode() + b"\0" + hashlib.sha256(f.read_bytes()).digest())
    return m.hexdigest()


def sh(c: str) -> str:
    return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    prefix, slots, deadline, mirror = sys.argv[1:5]
    E = pathlib.Path("/srv/eval")
    st = E / "staged"
    sc = E / "_selfcheck" / "selfcheck.json"
    banks = sorted(p.name for p in st.iterdir() if p.is_dir()) if st.exists() else []
    rec = {
        "prefix": prefix, "launched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "slots": int(slots), "deadline": deadline,
        "mirror": mirror, "tools_sha256": {f.name: h(f) for f in sorted(pathlib.Path("/opt/eval/bin").rglob("*")) if f.is_file()
                                          and "__pycache__" not in f.parts},
        "bridge_sha256": h(pathlib.Path("/opt/eval/bridge/ops/eval/native_acceptance_bridge.py")),
        "wheel": {f.name: h(f) for f in pathlib.Path("/opt/eval/wheel").glob("*.whl")},
        "staged_tree_sha256": {b: tree(st / b) for b in banks},
        "tasks_index_sha256": h(st / "tasks_index.json") if (st / "tasks_index.json").exists() else None,
        "staged_manifest_sha256": h(st / "MANIFEST.json") if (st / "MANIFEST.json").exists() else None,
        "selfcheck": json.loads(sc.read_text()) if sc.exists() else None,
        "model_safetensors_sha256": sh("sha256sum /content/gemma-4-12B-it-qat-w4a16-ct/model.safetensors 2>/dev/null | cut -d' ' -f1"),
        "vllm": sh("/content/venv-vllm/bin/python -c 'import vllm; print(vllm.__version__)' 2>/dev/null"),
        "pi": sh("PATH=/opt/eval/node/bin:$PATH /opt/eval/pi/bin/pi --version 2>&1 | tail -1"),
        "node": sh("/opt/eval/node/bin/node -v"), "tmux": sh("tmux -V"), "bwrap": sh("bwrap --version"),
        "python3": sh("python3 --version"), "kernel": sh("uname -r"),
        "gpu": sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"),
        "vllm_cmdline": sh("pgrep -af 'vllm serve' | grep -v pgrep | head -1 | cut -d' ' -f2-"),
        "fixed_variables": {"model": "gemma-4-12b-it-qat (vLLM served-model-name)", "thinking": "off (proxy think/off)",
                            "instruction": "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.",
                            "agent_timeout_s": 1800, "turn_cap": None, "terminal": "tmux 160x50, TERM=xterm-256color, history-limit 50000",
                            "pi_env": "PI_OFFLINE=1 (all arms)", "isolation": "fresh Linux user + bwrap per cell (sandbox.sh)"}}
    (E / "env_manifest.json").write_text(json.dumps(rec, indent=1) + "\n")
    (E / f"launch_record_{prefix}.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("prefix", "launched", "slots", "deadline", "pi", "tmux", "vllm")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
