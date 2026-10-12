#!/usr/bin/env python3
"""launch_record — 發射紀錄：把這一批用到的每樣東西的 sha256 與版本釘進 `/srv/eval/env_manifest.json`（packer 會打進 chunk）
和 `/srv/eval/launch_record_<前綴>.json`。對照第一批 launch_batch.sh 的內嵌 python，另加：tmux／bwrap 版本、bridge 檔、
selfcheck 摘要（含 bridge 墊片有沒有用）、題庫索引與 MANIFEST 的 sha256。

    python3 launch_record.py <前綴> <位置數> <時限 UTC> <鏡像目錄>
"""
from __future__ import annotations

import hashlib
import json
import os
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


def run(argv: list[str], env: dict[str, str] | None = None, last_line: bool = False) -> str:
    """固定的指令、不經 shell（版本字串都是寫死的指令，不吃外部輸入）；跑不起來回空字串。"""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60,
                           env={**os.environ, **env} if env else None)
    except (OSError, subprocess.SubprocessError):
        return ""
    out = (r.stdout + (r.stderr if last_line else "")).strip()
    return out.splitlines()[-1] if (last_line and out) else out


def fixed_variables(extra: list[str]) -> dict:
    """發射紀錄裡的「固定變數」。⚠ 牆鐘上限與 IDLE_S 取自**實際傳給 driver 的參數**（沒傳＝預設 1800／15），不是寫死的字串：
    2026-10-01 本機端到端用 `--agent-timeout 60` 跑，舊版紀錄仍寫 1800——紀錄說謊比沒有紀錄更糟。"""
    def opt(name: str, default):
        for i, a in enumerate(extra):
            if a == name and i + 1 < len(extra):
                return type(default)(extra[i + 1])
            if a.startswith(name + "="):
                return type(default)(a.split("=", 1)[1])
        return default
    return {"model": "gemma-4-12b-it-qat (vLLM served-model-name)", "thinking": "off (proxy think/off)",
            "instruction": "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.",
            "agent_timeout_s": opt("--agent-timeout", 1800), "idle_s": opt("--idle-s", 15.0), "max_units": opt("--max-units", 0) or None,
            "turn_cap": None, "terminal": "tmux 160x50, TERM=xterm-256color, history-limit 50000",
            "pi_env": "PI_OFFLINE=1 (all arms)", "isolation": "fresh Linux user + bwrap per cell (sandbox.sh)"}


def vllm_cmdline() -> str:
    lines = [ln for ln in run(["pgrep", "-af", "vllm serve"]).splitlines() if "pgrep" not in ln]
    return lines[0].split(" ", 1)[1] if lines and " " in lines[0] else ""


MODEL = pathlib.Path("/content/gemma-4-12B-it-qat-w4a16-ct/model.safetensors")


def main() -> int:
    prefix, slots, deadline, mirror = sys.argv[1:5]
    extra = sys.argv[5:]
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
        "model_safetensors_sha256": (h(MODEL) if MODEL.is_file() else ""),
        "vllm": run(["/content/venv-vllm/bin/python", "-c", "import vllm; print(vllm.__version__)"]),
        "pi": run(["/opt/eval/pi/bin/pi", "--version"],
                  env={"PATH": "/opt/eval/node/bin:" + os.environ.get("PATH", "")}, last_line=True),
        "node": run(["/opt/eval/node/bin/node", "-v"]), "tmux": run(["tmux", "-V"]),
        "bwrap": run(["bwrap", "--version"]),
        "python3": run(["python3", "--version"]), "kernel": run(["uname", "-r"]),
        "gpu": run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader"]),
        "vllm_cmdline": vllm_cmdline(),
        "driver_extra_args": extra,
        "fixed_variables": fixed_variables(extra)}
    (E / "env_manifest.json").write_text(json.dumps(rec, indent=1) + "\n")
    (E / f"launch_record_{prefix}.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("prefix", "launched", "slots", "deadline", "pi", "tmux", "vllm")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
