"""評測的 C 組：Harbor 官方的 pi agent，**加上使用者會打的安裝指令**，其他一個字都不改
（`decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md`；產品原則 3：不准為了評測另外接東西）。

    PYTHONPATH=<repo>/ops/eval VACANT_WHEEL=<wheel 路徑> uv run harbor run --agent harbor_vacant:PiWithVacant …

和 A 組（`--agent pi`）的差別只有 `install()` 多做的這幾件事：
1. 機器上沒有 pipx ⇒ 用系統的套件管理器裝（Ubuntu／Debian：`apt-get install pipx`）——README 叫使用者做的同一件事。
2. `pipx install <wheel>`（wheel 取代 PyPI 下載：PyPI 上還是舊版；依賴照樣從 PyPI 裝）。
3. `vacant install`，在 pi 可以被找到的殼層裡（Harbor 用 nvm 裝 pi），並且
   `PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent`——Harbor 用自訂端點時 pi 讀的是這個設定目錄
   （`harbor/agents/installed/pi.py` 的 `use_isolated_config`），裝在 `~/.pi/agent` 的擴充不會被載入。
   使用者的 pi 設定目錄在哪，`vacant install` 就裝到哪；這是配合評測框架的隔離，記在偏差欄。
**不設任何 Vacant 環境變數。**

`run()` 之後把 `~/.vacant` 整個複製到這一跑的紀錄目錄（`agent/vacant_home/`），再寫一份 `vacant_check.json`：
`install.json` 有沒有 pi、病歷裡有幾個步驟、幾次交件前檢查（`review` 事件）。沒裝上或沒有步驟＝**C 組失敗**
（照算 C 的成績），不是安靜地變成 A 組。沒有交件前檢查（`stop_reached=false`）另外報：回合用完被 Harbor 中止時
pi 不會進 Stop，那不是 Vacant 壞掉。
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path

from harbor.agents.installed.pi import _REMOTE_PI_CONFIG_DIR, Pi

_WHEEL_DIR = "/tmp/vacant-wheel"

_CHECK = r"""
import json, pathlib
h = pathlib.Path.home() / ".vacant"
out = {"install_json": None, "pi_installed": False, "chains": 0, "steps": 0, "reviews": 0,
       "review_actions": []}
p = h / "adapters" / "install.json"
if p.is_file():
    d = json.loads(p.read_text())
    out["install_json"] = {"mode": d.get("mode"), "agents": sorted((d.get("agents") or {}))}
    out["pi_installed"] = "pi" in (d.get("agents") or {})
for c in h.glob("trace/projects/*/chain.ndjson"):
    out["chains"] += 1
    for ln in c.read_text().split("\n"):
        if not ln.strip():
            continue
        e = json.loads(ln)
        if e.get("type") == "step":
            out["steps"] += 1
        elif e.get("type") == "review":
            out["reviews"] += 1
            out["review_actions"].append((e.get("payload") or {}).get("action"))
# 裝上了、病歷有步驟＝C 組有作用；有沒有走到交件前檢查另外記（回合用完被中止的跑，pi 不會進 Stop）
out["c_arm_ok"] = out["pi_installed"] and out["steps"] > 0
out["stop_reached"] = out["reviews"] > 0
print(json.dumps(out))
"""


class PiWithVacant(Pi):
    """名字、紀錄目錄、軌跡轉換都沿用 `Pi`（和 A 組一樣）；兩組靠不同的 jobs 目錄分開。"""

    async def install(self, environment) -> None:
        await super().install(environment)
        wheel = Path(os.environ["VACANT_WHEEL"]).resolve()
        await self.exec_as_root(environment, command=(
            "command -v pipx >/dev/null 2>&1 || "
            "(apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq pipx)"))
        await self.exec_as_agent(environment, command=f"mkdir -p {_WHEEL_DIR}")
        await environment.upload_file(wheel, f"{_WHEEL_DIR}/{wheel.name}")
        agent_dir = shlex.quote(_REMOTE_PI_CONFIG_DIR.as_posix())
        await self.exec_as_agent(environment, command=(
            "set -euo pipefail; . ~/.nvm/nvm.sh; export PATH=\"$HOME/.local/bin:$PATH\"; "
            f"pipx install {shlex.quote(f'{_WHEEL_DIR}/{wheel.name}')} && "
            f"mkdir -p {agent_dir} && PI_CODING_AGENT_DIR={agent_dir} vacant install"))

    async def run(self, instruction, environment, context) -> None:
        try:
            await super().run(instruction, environment, context)
        finally:
            logs = shlex.quote(str(self.environment_logs_dir))
            await self.exec_as_agent(environment, command=(
                f"cp -a \"$HOME/.vacant\" {logs}/vacant_home 2>/dev/null; "
                f"py=$(ls -d \"$HOME\"/.local/share/pipx/venvs/vacant-network/bin/python 2>/dev/null); "
                f"\"${{py:-python3}}\" -c {shlex.quote(_CHECK)} > {logs}/vacant_check.json 2>&1 || true"))
