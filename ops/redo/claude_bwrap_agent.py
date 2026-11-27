#!/usr/bin/env python3
"""claude_bwrap_agent — 控制器實驗（DECISION_20261127 修正 4）用：把 Claude Code headless worker 關進 bwrap。

這支在架構裡承重什麼
====================
原設計的 worker 是 pi＋本機 LM Studio（`ops/redo/bwrap_agent.sh`）。那台機器壞掉之後，擁有者指示改用
Claude Code headless（`claude -p --model haiku`）當 worker。本檔是 `ops/redo/redo.py` 計畫裡的
`agent.argv[0]`，做三件事：

1. **檔案系統隔離**：bwrap 最小 rootfs——唯讀的 `/usr`、`/etc`、claude CLI 安裝、pytest 的 venv、
   CLI 認證用的目錄（唯讀）；可寫的只有本次嘗試的工作區（固定掛在 `/work`）與 tmpfs 的 `/tmp`、HOME。
   題庫（含 `hidden/`）、repo、別的臂／別次嘗試的工作區、`/root`、`/home/user` 都**沒有掛進來**。
2. **網路隔離**：`--unshare-net`；唯一的出口是宿主端的白名單代理（`ops.e1.netproxy`，只放行
   `api.anthropic.com:443`），經由綁進沙箱的一個 UNIX socket＋沙箱內的 `ops/e1/proxy_bridge.py`。
   每一筆連線（放行與被拒）寫進 `{logs}/netproxy.jsonl`。
3. **工具面**：`--tools Bash,Read,Edit,Write,Glob,Grep`、`--disallowedTools WebFetch,WebSearch`、
   `--strict-mcp-config`、`--disable-slash-commands`、`--no-session-persistence`；環境變數 `--clearenv`
   後只放一份白名單（不帶 GH／雲端金鑰、不帶外層工作階段的行為設定）。

誠實邊界（改碼請保留）
----------------------
- worker 讀得到 CLI 的認證目錄（唯讀）：沒有它就打不了模型。這和 `ops/e1` 掛 `.credentials.json` 是同一種暴露。
- 白名單代理不解 TLS：保證的是「只連得到 `api.anthropic.com:443`」，不檢查裡面送了什麼。
- 驗收與評分是 harness 在**沙箱外**跑 worker 寫的程式碼（原設計也是）；本檔只管 worker 行程本身。
- 系統提示是 Claude Code 自己的（不是 pi 的）；CLI 版本、模型代號記在每次嘗試的 log 第一行 `system/init`。

用法（計畫檔）：`"argv": ["redo-claude-agent", "{logs}", "{model}", "{prompt}"]`，cwd＝工作區。
`redo-claude-agent` 是 PATH 上指到本檔的符號連結。`--probe -- <cmd…>` 在同一個沙箱裡跑任意指令（負控制用）。
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.e1.netproxy import AllowlistUnixProxy  # noqa: E402

BRIDGE = REPO / "ops" / "e1" / "proxy_bridge.py"
VENV = pathlib.Path(os.environ.get("REDO_WORKER_VENV", "/opt/ctl-venv"))
CLAUDE_ROOT = pathlib.Path(os.environ.get("REDO_CLAUDE_ROOT", "/opt/claude-code"))
CA_BUNDLE = pathlib.Path("/root/.ccr/ca-bundle.crt")
TOOLS = "Bash,Read,Edit,Write,Glob,Grep"
DISALLOWED = "WebFetch,WebSearch"
ALLOWED_CONNECT = (("api.anthropic.com", 443),)
# 外層環境只放這些進沙箱（其餘一律不帶）。CLAUDE_CODE_REMOTE* 與 token 檔路徑是這個容器裡 CLI 認證所需。
ENV_PASS_EXACT = ("ANTHROPIC_BASE_URL", "CLAUDE_SESSION_INGRESS_TOKEN_FILE", "CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST",
                  "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_USE_CCR_V2", "CLAUDE_CODE_REMOTE",
                  "CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE", "CLAUDE_CODE_REMOTE_SESSION_ID",
                  "CLAUDE_CODE_ACCOUNT_UUID", "CLAUDE_CODE_ORGANIZATION_UUID", "CLAUDE_CODE_USER_EMAIL",
                  "CLAUDE_CODE_CONTAINER_ID", "IS_SANDBOX")


def sandbox_argv(ws: pathlib.Path, sock: pathlib.Path, cmd: list[str]) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SystemExit("claude_bwrap_agent: 找不到 bwrap")
    tok = os.environ.get("CLAUDE_SESSION_INGRESS_TOKEN_FILE")
    argv = [bwrap, "--die-with-parent", "--unshare-net", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--clearenv", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc",
            "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/sbin", "/sbin",
            "--ro-bind", str(CLAUDE_ROOT), str(CLAUDE_ROOT),
            "--ro-bind", str(BRIDGE), "/opt/bin/proxy_bridge.py",
            "--bind", str(sock), "/sandbox_proxy/proxy.sock",
            "--tmpfs", "/sandbox_home"]
    if VENV.is_dir():
        argv += ["--ro-bind", str(VENV), str(VENV)]
    if CA_BUNDLE.is_file():
        argv += ["--ro-bind", str(CA_BUNDLE), str(CA_BUNDLE)]
    if tok:
        td = str(pathlib.Path(tok).parent)
        argv += ["--ro-bind", td, td]
    argv += ["--bind", str(ws), "/work", "--chdir", "/work"]
    env = {"HOME": "/sandbox_home", "TMPDIR": "/tmp", "PWD": "/work", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "PATH": f"{VENV}/bin:{CLAUDE_ROOT}/bin:/usr/local/bin:/usr/bin:/bin",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
           "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    if CA_BUNDLE.is_file():
        env["NODE_EXTRA_CA_CERTS"] = str(CA_BUNDLE)
    for k in ENV_PASS_EXACT:
        if os.environ.get(k) is not None:
            env[k] = os.environ[k]
    for k, v in sorted(env.items()):
        argv += ["--setenv", k, v]
    return argv + ["--", "python3", "/opt/bin/proxy_bridge.py", "--sock", "/sandbox_proxy/proxy.sock", "--", *cmd]


def claude_cmd(model: str, prompt: str) -> list[str]:
    return ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model", model,
            "--permission-mode", "bypassPermissions", "--tools", TOOLS, "--allowedTools", TOOLS,
            "--disallowedTools", DISALLOWED, "--no-session-persistence", "--strict-mcp-config",
            "--disable-slash-commands", "--", prompt]


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "--probe":
        logs = pathlib.Path(argv[0])
        cmd = argv[3:] if argv[2] == "--" else argv[2:]
    elif len(argv) == 3:
        logs = pathlib.Path(argv[0])
        cmd = claude_cmd(argv[1], argv[2])
    else:
        print("usage: redo-claude-agent <logs> <model> <prompt> | <logs> --probe -- <cmd…>", file=sys.stderr)
        return 2
    logs.mkdir(parents=True, exist_ok=True)
    ws = pathlib.Path.cwd().resolve()
    with AllowlistUnixProxy(allowed_connect=ALLOWED_CONNECT, log_path=logs / "netproxy.jsonl") as px:
        proc = subprocess.Popen(sandbox_argv(ws, px.sock_path, cmd), stdin=subprocess.DEVNULL)
        try:
            return proc.wait()
        except KeyboardInterrupt:
            proc.kill()
            return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
