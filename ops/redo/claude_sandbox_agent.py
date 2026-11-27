#!/usr/bin/env python3
"""claude_sandbox_agent — 控制器實驗（DECISION_20261127 修正 4）：Claude Code headless worker 的隔離包裝。

這支在架構裡承重什麼
====================
原設計的 worker 是 pi＋本機 LM Studio（`ops/redo/bwrap_agent.sh`，bwrap 關進去）。機器損毀後改用
`claude -p --model haiku`。本檔是 `ops/redo/redo.py` 計畫裡的 `agent.argv[0]`（PATH 上的符號連結
`redo-claude-agent`），cwd＝這一次嘗試的工作區：

    redo-claude-agent <logs> <model> <prompt>

為什麼不是「整個 CLI 關進 bwrap」（接手時留下的草稿做法，已移除）
----------------------------------------------------------------
這個容器裡 CLI 的認證來自固定路徑 `/home/claude/.claude/remote/.oauth_token`（strace 看到的）。
把整個 CLI 連同 worker 的 Bash 一起關進 bwrap，就得把這個權杖檔掛進沙箱，worker 的指令讀得到它——
自動模式分類器正確地擋下了這個做法（未授權的憑證暴露）。所以改成**兩層**：

1. CLI 行程本身在沙箱外（它自己持有認證、自己連 api.anthropic.com）。
2. worker **能動手的面**才是被隔離的：
   - **Bash**：用 CLI 內建的作業系統層沙箱（bubblewrap，`sandbox.enabled`，`failIfUnavailable`，
     `allowUnsandboxedCommands=false`）：檔案讀取 deny `/home /root /opt/ctlwork /mnt /srv /tmp /var/tmp`
     與工作區根目錄、**只 allowRead／allowWrite 這一次嘗試的工作區**；網路預設全擋（沒有白名單網域）。
   - **Read／Edit／Write／Glob／Grep**：**不**放行裸工具名；只靠 CLI 預設的「cwd 之內才自動允許、之外要求權限」
     （-p 模式沒人回答＝拒絕），另加明確的 deny 規則（題庫、repo、/root、/home、/opt/ctlwork、/mnt）當第二道。
   - `--disallowedTools WebFetch,WebSearch`、`--strict-mcp-config`、`--disable-slash-commands`、
     `--no-session-persistence`、`--setting-sources ""`（不載任何使用者／專案設定）。
3. CLI 的環境變數**全清**（只放 PATH／HOME／LANG）；HOME 是每次嘗試自己的目錄（放在 logs 底下）。

誠實邊界（改碼請保留）
----------------------
- **Read／Edit／Write／Glob／Grep 是 CLI 行程內的規則，不是作業系統隔離**；只有 Bash 是 OS 沙箱。
  規則靠 CLI 實作正確。負控制（`ops/redo/claude_negctl.py`）逐一實測，但那是抽樣不是證明。
- CLI 行程（含它的網路）不在沙箱內：worker 的 Bash 沒有網路，但 CLI 自己連得到 API；模型回應內容不受檢查。
- worker 的指令碰不到認證檔（在被 deny 的 /home 底下），但**CLI 行程**當然讀得到。
- 驗收與評分是 harness 在沙箱外跑 worker 寫的程式碼（原設計也是）。
- 系統提示是 Claude Code 自己的；CLI 版本與模型代號記在每次嘗試 log 第一行 `system/init`。
- Haiku 訓練資料可能含 Exercism 參考解（無法排除）；WebFetch／WebSearch 已禁用、Bash 無網路。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

VENV = os.environ.get("REDO_WORKER_VENV", "/opt/ctl-venv")
# Bash 沙箱的 deny 讀取根（工作區根目錄由環境變數 REDO_WS_ROOT 另加）
DENY_READ = ["/home", "/root", "/opt/ctlwork", "/mnt", "/srv", "/tmp", "/var/tmp"]
PERM_DENY_PATHS = ["/home", "/root", "/opt/ctlwork", "/mnt", "/srv"]
TOOLS_ALLOWED = ["Bash"]            # 其餘工具只靠預設的 cwd 規則（見模組 docstring）
TOOLS_AVAILABLE = "Bash,Read,Edit,Write"   # 這版 CLI 預設還有 Task／Cron*／RemoteTrigger／Workflow／SendMessage…；全部移除
                                           # （這版沒有獨立的 Glob／Grep 工具，搜尋走 Bash 的 find／grep）
TOOLS_DISALLOWED = ["WebFetch", "WebSearch"]


def build_settings(ws: pathlib.Path, ws_root: pathlib.Path | None) -> dict:
    deny_read = list(DENY_READ)
    if ws_root is not None:
        deny_read.append(str(ws_root))
    perm_deny: list[str] = []
    for p in PERM_DENY_PATHS:
        for tool in ("Read", "Edit"):          # Edit 規則涵蓋 Write；Read 規則涵蓋 Glob／Grep
            perm_deny.append(f"{tool}(/{p}/**)")   # `//abs` ＝ 絕對路徑
    perm_deny += ["WebFetch", "WebSearch"]
    return {
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {"denyRead": deny_read, "allowRead": [str(ws)], "allowWrite": [str(ws)]},
        },
        "permissions": {"deny": perm_deny},
    }


def claude_argv(model: str, prompt: str, settings: pathlib.Path) -> list[str]:
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model", model,
            "--tools", TOOLS_AVAILABLE, "--setting-sources", "", "--settings", str(settings),
            "--permission-mode", "acceptEdits", "--allowedTools", ",".join(TOOLS_ALLOWED),
            "--disallowedTools", ",".join(TOOLS_DISALLOWED), "--no-session-persistence",
            "--strict-mcp-config", "--disable-slash-commands", "--", prompt]


def clean_env(home: pathlib.Path) -> dict[str, str]:
    return {"PATH": f"{VENV}/bin:/usr/local/bin:/usr/bin:/bin:/opt/claude-code/bin", "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_TELEMETRY": "1"}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: redo-claude-agent <logs> <model> <prompt>", file=sys.stderr)
        return 2
    logs, model, prompt = pathlib.Path(argv[0]), argv[1], argv[2]
    logs.mkdir(parents=True, exist_ok=True)
    ws = pathlib.Path.cwd().resolve()
    root = os.environ.get("REDO_WS_ROOT")
    settings = logs / "claude_settings.json"
    settings.write_text(json.dumps(build_settings(ws, pathlib.Path(root).resolve() if root else None),
                                   indent=1), encoding="utf-8")
    home = logs / "home"
    home.mkdir(exist_ok=True)
    proc = subprocess.Popen(claude_argv(model, prompt, settings), cwd=str(ws), env=clean_env(home),
                            stdin=subprocess.DEVNULL)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.kill()
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
