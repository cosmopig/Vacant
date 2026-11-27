#!/usr/bin/env python3
"""devin_sandbox_agent — 控制器實驗（DECISION_20261127 雲端修正 C5）：Devin CLI（免費模型）worker 的隔離包裝。

這支在架構裡承重什麼
====================
`ops/redo/redo.py` 計畫裡的 `agent.argv[0]`（PATH 上的符號連結 `redo-devin-agent`），cwd＝這一次嘗試的工作區：

    redo-devin-agent <logs> <model> <prompt>

介面與 `claude_sandbox_agent.py` 相同。`logs/devin_export.json`（ATIF 匯出）是用量的來源
（`redo.usage_from_devin_log`）；`logs/devin_settings.json` 是這一次實際用的設定；
`logs/devin_wrapper.json` 記 CLI 版本、模型、argv（不含 prompt 全文）。

隔離設計（和 Claude 版同一個原則：CLI 行程在外、worker 能動手的面被限制）
---------------------------------------------------------------------------
- 認證檔（`/root/.local/share/devin/credentials.toml`）留在原處，HOME＝真的 /root（CLI 自己要讀）。
  **不複製、不掛進任何 worker 工具讀得到的地方**；worker 的工具靠 deny 規則＋exec 沙箱碰不到 /root。
- `--sandbox`（Devin 內建，Linux bwrap＋seccomp，研究預覽）：exec 工具的行程只能寫工作區，讀取＝
  「除了 Deny(Read(...)) 規則隱藏的路徑以外都能讀」；網路走沙箱自己的 proxy（沒有白名單網域＝連不出去）。
  ⚠ `--sandbox` 一律用 autonomous 權限模式（CLI 會忽略 --permission-mode）。
- 設定檔（`--config`，每次嘗試一份）的 `permissions.deny`：
  Read／Write 的受保護根目錄（/root /home /opt /mnt /srv /tmp /var/tmp）＋兄弟工作區。
  **deny 優先於 allow、而且「精確目錄」的 deny 會連祖先一起擋（實測：deny /var/ctlws 讓 cwd 在底下的 exec 全被拒）**，
  所以兄弟工作區不能用 `/var/ctlws/**` 擋。工作區名是 `redo-` ＋ 8 個隨機字元（mkdtemp）；
  這裡逐位置展開：對每個位置 i、每個不等於自己第 i 個字元的字元 ch，deny `<root>/<自己前 i 個>ch*` 與其 `/**`。
  共 8×36 條（另加一般前綴 `redo-` 以外的字首由字母表涵蓋），涵蓋**所有現在與未來**的兄弟、只放過自己。
- 網頁：`Fetch(domain:*)`、`Fetch(https://**)`、`Fetch(http://**)`、`web_search` 都 deny（實測：`WebFetch`／`Fetch(*)`／`Fetch(**)` 是**無效**的規則名）。
- **mount namespace（bwrap，整個 CLI 行程）**：/home、/opt/ctlwork、/mnt、/srv、工作區根目錄都是空 tmpfs，只綁回自己的
  工作區上層與 logs。所以兄弟工作區（含未來才建立的）、題庫、repo、隱藏半邊在**所有工具**眼裡都不存在——上面的兄弟 deny 規則只是第二道。
  （實測：只靠 deny 規則時 exec 內的 `python open()` 讀得到兄弟工作區；glob 規則不會被 Devin 展開進 exec 沙箱。）
- CLI 環境變數全清（只放 PATH／HOME／LANG＋容器代理，那是 CLI 連 Devin 服務所需；代理 URL 不含帳密）。
- 專案設定：`--config` 取代使用者設定檔；cwd 的 `.devin/config*.json` 是 CLI 自己的寫入保護名單。

誠實邊界（改碼請保留；實測見 `ops/redo/devin_negctl.py` 與 results 的 NEGCTL.md）
------------------------------------------------------------------------------
- 作業系統層（bwrap）只管 **exec 工具**；read／write／edit／grep／find_file_by_name／notebook_* 是 CLI 行程內的規則。
- 「規則」類的 exec 檢查是字串＋路徑比對，exec 內的 `python -c open(...)` 靠 bwrap 的 Deny(Read) 隱藏擋（實測 FileNotFoundError）。
- 兄弟工作區的**目錄名**列得出來（`ls <root>` 成功，內容讀不到）。
- CLI 行程本身（含網路、認證）不在沙箱內；模型回應內容不受檢查。
- 子 agent（run_subagent）是否繼承 deny：負控制有探針；mcp_* 沒設任何伺服器。
- 遠端服務端是 Devin 雲端；模型別名之後可能指向別的版本。
"""
from __future__ import annotations

import json
import os
import pathlib
import random
import re as _re
import subprocess
import sys
import time

DEVIN = os.environ.get("REDO_DEVIN_BIN", "/root/.local/bin/devin")
PROTECTED = ["/root", "/home", "/opt", "/mnt", "/srv", "/tmp", "/var/tmp"]
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789_-"
FREE_MODELS_RE = r"^(swe-2-flash-(medium|high|max)|swe-2-(medium|high|max)|swe-2-1(-(low|medium|high|xhigh|max))?)$"
COOLDOWN = pathlib.Path(os.environ.get("REDO_DEVIN_COOLDOWN", "/var/ctlws_devin/.devin_cooldown"))
RESET_RE = _re.compile(r"reset in (\d+) (second|minute|hour)")
PROXY_KEYS = ("HTTPS_PROXY", "https_proxy", "SSL_CERT_FILE", "NO_PROXY")


def sibling_denies(ws: pathlib.Path) -> list[str]:
    """工作區 `<root>/redo-XXXXXXXX/w`：擋掉 root 底下所有名字和自己不同的項目（現在與未來）。"""
    top = ws.parent                      # <root>/redo-XXXXXXXX
    root, name = str(top.parent), top.name
    out: list[str] = []
    for i in range(len(name)):
        for ch in ALPHABET:
            if ch == name[i]:
                continue
            pat = f"{root}/{name[:i]}{ch}*"
            out += [f"Read({pat})", f"Read({pat}/**)", f"Write({pat}/**)"]
    # 同一個 redo-XXXXXXXX 之下、自己以外的東西（agentcfg 等）
    return out


def build_settings(ws: pathlib.Path, extra_deny_read: list[str] | None = None) -> dict:
    deny: list[str] = []
    for p in PROTECTED + list(extra_deny_read or []):
        deny += [f"Read({p}/**)", f"Write({p}/**)", f"Edit({p}/**)"]
    deny += sibling_denies(ws)
    deny += ["Fetch(domain:*)", "Fetch(https://**)", "Fetch(http://**)", "web_search"]
    allow = ["Exec(*)", f"Read({ws}/**)", f"Write({ws}/**)", f"Edit({ws}/**)"]
    return {"version": 1, "respect_workspace_trust": False, "permissions": {"allow": allow, "deny": deny}}


def clean_env() -> dict[str, str]:
    env = {"PATH": "/root/.local/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/root", "LANG": "C.UTF-8",
           "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}
    venv = os.environ.get("REDO_WORKER_VENV", "/opt/ctl-venv")
    env["PATH"] = f"{venv}/bin:" + env["PATH"]
    for k in PROXY_KEYS:
        if os.environ.get(k):
            env[k] = os.environ[k]
    if os.environ.get("SSL_CERT_FILE"):
        env["NODE_EXTRA_CA_CERTS"] = os.environ["SSL_CERT_FILE"]
    return env


def mount_ns_prefix(ws: pathlib.Path, logs: pathlib.Path) -> list[str]:
    """整個 CLI 行程（含它所有工具）在自己的 mount namespace 裡：把 /home、/opt/ctlwork、/mnt、/srv、/tmp、
    工作區根目錄蓋成空的 tmpfs，只把**這一次嘗試自己的**工作區上層目錄與 logs 目錄綁回原路徑。
    這是作業系統層、對所有工具（read／grep／find／notebook／子 agent／exec）一體適用，包含「未來才建立的兄弟工作區」。
    不蓋 /root：CLI 要讀自己的認證檔（沒有它打不了模型）——/root 靠 deny 規則（檔案工具）＋Devin exec 沙箱（exec）擋。
    """
    top = ws.parent
    root = top.parent
    return ["bwrap", "--bind", "/", "/", "--dev-bind", "/dev", "/dev", "--tmpfs", "/home", "--tmpfs", "/opt/ctlwork",
            "--tmpfs", "/mnt", "--tmpfs", "/srv", "--tmpfs", str(root), "--bind", str(top), str(top),
            "--bind", str(logs), str(logs), "--die-with-parent", "--"]


def devin_argv(model: str, prompt: str, settings: pathlib.Path, export: pathlib.Path) -> list[str]:
    return [DEVIN, "-p", "--respect-workspace-trust", "false", "--config", str(settings), "--sandbox",
            "--process-model", "in-process", "--model", model, "--export", str(export), "--", prompt]


def main(argv: list[str]) -> int:
    import re
    if len(argv) != 3:
        print("usage: redo-devin-agent <logs> <model> <prompt>", file=sys.stderr)
        return 2
    logs, model, prompt = pathlib.Path(argv[0]), argv[1], argv[2]
    if not re.match(FREE_MODELS_RE, model):
        print(f"refused: {model!r} is not on the free-model allowlist", file=sys.stderr)
        return 2
    logs.mkdir(parents=True, exist_ok=True)
    ws = pathlib.Path.cwd().resolve()
    settings, export = logs / "devin_settings.json", logs / "devin_export.json"
    settings.write_text(json.dumps(build_settings(ws), indent=1), encoding="utf-8")
    try:
        ver = subprocess.run([DEVIN, "--version"], capture_output=True, text=True, timeout=20, env=clean_env()).stdout.strip()
    except Exception as e:  # noqa: BLE001
        ver = f"unknown ({e})"
    (logs / "devin_wrapper.json").write_text(json.dumps({"cli": ver, "model": model, "workspace": str(ws),
                                                         "argv": devin_argv(model, "<prompt>", settings, export)}, indent=1))
    # 限流冷卻（雲端修正 C6 第 3 點）：任一嘗試遇到「Your limit will reset in N …」就把截止時間寫進共用檔；之後起跑的嘗試先睡到截止時間，
    # 再以限流錯誤結束（⇒ harness 當 infra 失敗、不算嘗試；睡眠發生在 devin 起跑之前，但仍在這次嘗試的牆鐘內，而這次嘗試會被丟棄）。
    now = time.time()
    try:
        cool = float(COOLDOWN.read_text())
    except (OSError, ValueError):
        cool = 0.0
    if cool > now:
        time.sleep(cool - now + random.uniform(2, 20))
        print(f"Error: Agent error: Reached free model rate limit (wrapper: waited {cool - now:.0f}s for the shared cooldown; no model call made)", flush=True)
        return 75
    cmd = mount_ns_prefix(ws, logs.resolve()) + devin_argv(model, prompt, settings, export)
    proc = subprocess.Popen(cmd, cwd=str(ws), env=clean_env(), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    try:
        seen = []
        for line in proc.stdout:            # 原樣轉給 harness 的 agent.log，同時找限流訊息
            sys.stdout.write(line)
            sys.stdout.flush()
            m = RESET_RE.search(line)
            if m:
                n = int(m.group(1)) * {"second": 1, "minute": 60, "hour": 3600}[m.group(2)]
                seen.append(n)
        rc = proc.wait()
        if seen:
            try:
                COOLDOWN.write_text(str(max(float(COOLDOWN.read_text() or 0) if COOLDOWN.exists() else 0, time.time() + max(seen) + 15)))
            except (OSError, ValueError):
                pass
    except KeyboardInterrupt:
        proc.kill()
        rc = 130
    try:        # 憑證衛生（雲端修正 C6）：每次嘗試結束後掃工作區與 logs；被逾時殺掉時 wrapper 也死，那種格靠整批結束後的整根掃描補
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import credscan
        (logs / "credscan.json").write_text(json.dumps(credscan.scan([ws, logs]), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        (logs / "credscan.json").write_text(json.dumps({"error": str(e)}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
