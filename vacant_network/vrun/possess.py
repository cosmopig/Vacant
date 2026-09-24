"""這支在架構裡承重什麼：**把 Vacant 從「每次要打的包裝器」變成「裝一次就在」。**

在這支之前，用 Vacant 的形狀是

    vacant run --suite <目錄> -- pi -p "做這件事"

**最大的洞不是 unix socket，是使用者忘記打那一串**——忘了就完全沒有 Vacant，
而且**零痕跡**。本模組把形狀改成

    vacant install          # 裝一次
    pi -p "做這件事"         # 之後照舊

---

## 兩層，能保證的東西不一樣（⚠ 不可以混講成一句「附身成功」）

| 層 | 機制 | 能說的話 |
|---|---|---|
| **通道** | 寫進 agent **自己的常駐設定檔**（`~/.claude/settings.json` 的 `env`、`~/.codex/config.toml`、`~/.config/opencode/opencode.json`、`~/.pi/agent/extensions/vacant.ts`（2026-09-22 起；不再碰 `models.json`）、`~/.hermes/config.yaml`） | 關終端機、重開機、開新視窗、**打完整路徑**都照樣指向 proxy。**只有把那幾行刪掉才會失效。** |
| **閘門** | `PATH` shim（`~/.vacant/possess/bin/` 排在 `PATH` 前面） | **預設會跑，但打完整路徑就跳過了。** |

⚠ **本檔任何一處都不准寫「不會被繞過」。** 閘門層做不到；通道層做得到的是
「設定檔沒被改回去之前都在」，那也不是「不可繞過」——同一個 OS 使用者隨時
可以自己把那幾行刪掉，或者用一個不在名單上的 agent
（`vacant_network/controller.py:7-8` 的同一條邊界）。

## 三個設計選擇，理由寫在這裡（裁決檔＝`decisions/DECISION_20260919_DEFAULT_ON_INSTALL.md`）

### 1. 沒有 `--suite` 的時候驗收從哪來

`possess.resolve_suite()` 由近而遠找，**第一個命中就停**，而且把「是哪一條規則
命中的」記進收據（`suite_source`）：

  1. `$VACANT_SUITE`（明講）
  2. 從 cwd 往上走，找 `.vacant/suite/`
  3. 從 cwd 往上走，找 `.vacant.toml` 裡的 `suite = "..."`
  4. 從 cwd 往上走，找 `tests_visible/`（本 repo 的 R530／R535 題庫慣例）

**都沒有 ⇒ 只中介不跑閘門**，而不是拒絕啟動。理由：使用者在一個沒有測試的
目錄裡打 `pi -p "這段在做什麼"` 是正常的，拒絕啟動會讓人把 Vacant 解除安裝，
**而解除安裝之後是零個 Vacant，比只有通道層更糟**。

⚠ **但「只中介」必須在收據與退出碼上跟「跑了驗收而且過了」分得出來**，
這是本模組最硬的一條紀律（2026-09-19 人類點名）：

  · `stop_reason = "ungated"`、`accepted = null`（launcher 既有語意，沒動）
  · **退出碼 `21`**，不是 `0`。`0` 保留給「驗收真的跑了而且過了」。
  · `suite_source = "none"` 落進收據。

### 2. 通道寫進使用者自己的檔，還是 Vacant 自己管一份

**通道層寫進使用者自己的檔**（不然就不是「預設在」）；**閘門層 Vacant 自己
管一份**（shim 目錄，不動任何 agent 的設定）。

寫使用者的檔是有代價的，所以三件事一起做，缺一不可：

  · **先備份**：原始 bytes 整個複製到 `<state>/backups/`，記 sha256。
  · **`vacant install-status` 講得出改了什麼**：逐檔列出 before/after sha256、
    備份在哪、還原會做什麼。
  · **`vacant uninstall` 逐位元還原**，而且**還原之後自己驗一次 sha256**，
    對不上就大聲說（不是安靜地當作成功）。

### 3. proxy 常駐還是隨跑隨起 ⇒ **常駐，而且 fail-closed**

設定檔寫死一個端點 ⇒ 那個端點必須隨時在。所以 `vacant install` 會裝一個
**由 OS 監督的常駐 proxy**（macOS `launchd` 的 `RunAtLoad`＋`KeepAlive`；
Linux `systemd --user` 的 `Restart=always`＋`enable-linger`），而不是每次
shim 自己起一個——shim 只在「有人經過 shim」時才存在，那正是繞得過的那一層。

**proxy 沒起來的時候 agent 應該連不上而報錯（fail-closed），不是回退直連。**
四個理由：

  a. 回退直連＝**安靜地失去中介**，那就是本模組存在要修掉的那個洞
     （`envmap` 誠實邊界 2：漏掉的那條路要**連不上**，不是**偷偷連上**）。
  b. 本 repo 每一處都是這條紀律：`SINK_UPSTREAM`（沒人指定上游 ⇒ 開連線之前
     就 502）、`no_suite` ⇒ 拒交、R440G 的 `--decision` 檔不存在 ⇒ 拒絕啟動。
     這裡破例會讓那幾條的口徑一起鬆掉。
  c. 失敗是**看得見而且定位得到**的：agent 印 connection refused，
     `vacant install-status` 直接說 proxy 沒在聽，`vacant uninstall` 一行復原。
  d. **技術上也沒有誠實的 fail-open**：要回退直連，就得在失敗當下把使用者的
     設定檔改回去——也就是這個工具要會**安靜地把自己解除安裝**。

⚠ **代價要講在前面**：proxy 起不來（埠被佔、python 壞掉、公司政策擋
launchd）⇒ **這台機器上五個 agent 全部不能用**，直到 `vacant uninstall`。
緩解有三：(i) `install` 有 **preflight**——先把 proxy 起起來、真的打一通
round-trip，**過了才寫任何一個設定檔**，所以不會因為設定錯而把人鎖在門外；
(ii) `uninstall` 是純檔案還原，**proxy 死著也跑得完**；
(iii) `install-status` 一眼看得出是哪一層壞了。

---

## 誠實邊界（改碼請保留）

1. **「我寫了設定檔」不是「被中介了」。** 唯一算數的證據是 proxy 的
   `requests_seen`（`envmap` 誠實邊界 1）。`install-status` 因此把每個 agent
   的通道分成 `wired`（檔案寫了）與 `proven`（真的看過 `requests_seen > 0`）
   兩欄，**永遠不把前者說成後者**。
2. **五個 agent 的接線不是同一級的證據。** `CONFIG_ROUTE` 的 `measured` 欄
   記的是「`vacant run` 那條路」量過的日期；**常駐設定檔那條路是另一條路**，
   本模組逐個 agent 另外記（`CHANNEL_MEASURED`）。沒量過的格子在
   `install-status` 上會標 `unverified`，不准讀成可用。
   **PATH shim 那條又是第三條路**（`SHIM_MEASURED`）：shim 在這一跑自己的設定目錄裡
   起 agent，常駐設定檔不在路上，所以 shim 的真模型成績**不准拿來點亮**
   `CHANNEL_MEASURED`（2026-09-22 pi 那格就犯過一次，已撤回）。
3. **憑證一律不讀不寫。** `~/.codex/auth.json`、`~/.pi/agent/auth.json`、
   keychain、`~/.claude/.credentials.json` 都在 `NEVER_TOUCH` 裡，
   而且常駐 proxy 是**原樣轉送 Authorization header**（不換鑰、不存鑰）——
   `wireproxy` 只把 **body** 落盤，header 不落盤。
4. **偵測不能只靠 PATH。** 兩台機器上都量到 agent 裝了但不在登入 PATH 上
   （vacant-dev 的 pi／opencode／hermes、人類 Mac 的 pi）。所以偵測是
   **設定目錄優先**，PATH 只是補充，而且 PATH 探測要用 `bash -lic`
   並且**把終端機的跳脫序列剝掉**（人類的 shell prompt 會把 OSC 7 混進
   `command -v` 的輸出裡，照單全收會拿到一個不存在的路徑）。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterable

from . import envmap

# ── 常數 ────────────────────────────────────────────────────────────────

#: 裸 `vacant` 引導安裝會提議的 agent。**只放走 extension、不改寫使用者既有 provider
#: 的那幾格**（今天只有 pi）；其他 agent 的接線會改寫使用者的常駐設定，要人明講
#: `vacant install --agent <x>`。
INSTALL_GUIDED_AGENTS: tuple[str, ...] = ("pi",)

#: 預設的常駐 proxy 埠。被佔用時 `install` 會往上找，**實際用的埠記進 state**。
DEFAULT_PORT = 8787

#: 絕對不讀也不寫的路徑（相對 HOME）。紅線，不是慣例。
NEVER_TOUCH: tuple[str, ...] = (
    ".codex/auth.json",
    ".pi/agent/auth.json",
    ".claude/.credentials.json",
    ".config/opencode/auth.json",
    ".hermes/auth.json",
    ".local/share/opencode/auth.json",
)

#: 本模組自己的狀態家。`VACANT_POSSESS_HOME` 可以整包搬走（測試用）。
def state_home(home: pathlib.Path | None = None) -> pathlib.Path:
    env = os.environ.get("VACANT_POSSESS_HOME")
    if env:
        return pathlib.Path(env).expanduser()
    base = home if home is not None else pathlib.Path.home()
    return base / ".vacant" / "possess"


#: 通道層「寫進常駐設定檔」這條路，**逐個 agent 的實測日期**。
#:
#: ⚠ 跟 `envmap.CONFIG_ROUTE[...]["measured"]` **不是同一件事**：那一欄記的是
#:   「`vacant run` 用 relocate 變數搬走設定」那條路；本表記的是「直接寫使用者
#:   自己那一份常駐設定檔、然後不經任何 Vacant 指令直接打 agent」那條路。
#:   兩條路的失效方式不同（relocate 那條漏了會回到使用者的設定；本條漏了
#:   會讓 agent 照舊直連），所以日期要分開記。空字串＝**沒量過**。
#: ⚠ 版本**要連機器一起講**（AGENT_COMPAT §13.1 的教訓：換機器結論就變）。
#:   下面三格全部是 2026-09-19 在**人類的 macOS 15（Darwin 24.6）**上量的，
#:   上游＝1003 的 LM Studio（`gemma-4-12b-it-qat`），
#:   量法＝**寫進常駐設定檔之後用完整路徑直接打 agent**，命令列上零個 vacant，
#:   證據＝常駐 proxy journal 的通數（不是「我設了設定」）。
#: ⚠ 一格裡有兩台機器的時候**兩個都要寫出來**，不可以併成一個數字：
#:   兩輪的 agent 版本、上游、模型服務實例都不同
#:   （`DECISION_20260919_DEFAULT_ON_INSTALL.md` §七-4）。
CHANNEL_MEASURED: dict[str, str] = {
    # codex-cli 0.153.2：`POST /v1/responses -> 200` ×4（另 1 通 400 後自行重試）
    # ⚠ Linux 那一格有一個前提：**登入環境要有 `OPENAI_API_KEY`**。沒有的話
    #   codex 在開連線之前就 `Missing environment variable` ⇒ journal 零通
    #   （2026-09-20 在 vacant-dev 上量到，裁決檔 §六.4-E）。
    "codex": "2026-09-19（macOS，codex-cli 0.153.2，5 通）"
             "／2026-09-20（vacant-dev Ubuntu 24.04，codex-cli 0.147.0，3 通，"
             "**需要 OPENAI_API_KEY 有值**）",
    # opencode 1.18.31：走我們加的 `vacant` provider，2 通，模型回了 OK
    "opencode": "2026-09-19（macOS，opencode 1.18.31，2 通）",
    # Claude Code 2.1.278：`~/.claude/settings.json` 的 `env` 區塊，
    # `POST /v1/messages?beta=true -> 200` ＋ 啟動探測 `HEAD /api/hello`
    # ⚠ Linux 那一格是在**隔離 HOME** 上量的（那台有人類的長壽 session 在跑
    #   Claude Code，不准動真的 settings.json），而且測試時另外補了
    #   `ANTHROPIC_API_KEY`——`wire_claude` 自己**不寫任何金鑰欄位**。
    # ⚠ 2026-09-22 第三格是在 **Claude Code 遠端容器裡、由 Claude Code 自己**量的
    #   （`ops/vacantrun/possess_claude_20260922/`，Haiku 4.5，真上游 api.anthropic.com）：
    #   `settings.json` 的 `env.ANTHROPIC_BASE_URL` 在
    #   **`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` 的環境下被忽略**（三格 E／D 零通、C 拆掉
    #   那個變數就 2 通）；環境變數那條照樣通。shim 那條拒交 20／交付 0 各 `requests_seen=10`。
    "claude": "2026-09-19（macOS，Claude Code 2.1.278，2 通）"
              "／2026-09-20（vacant-dev Ubuntu 24.04，Claude Code 2.1.259，3 通，"
              "**隔離 HOME**）"
              "／2026-09-22（Claude Code 遠端容器，2.1.278，Haiku 4.5，settings 路 2 通，"
              "**但 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` 時 settings.json 被忽略**）",
    # ⚠ 這兩格**沒量**：那台機器上沒有 pi／hermes 的可執行檔（pi 只有設定目錄）。
    #   寫進設定檔的碼跑過了，但**沒有任何 `requests_seen` 證實它有效**。
    # ⚠ pi 這一格**到今天仍是空的**，而且是刻意的：本表記的是 `wire_pi` 寫的那支
    #   **常駐 extension**（`~/.pi/agent/extensions/vacant.ts` → 常駐 proxyd）這條路。
    #   - 常駐 extension 那條只有 **L-fake**（`ops/vacantrun/possess_pi_20260922/`，假上游）。
    #   - 2026-09-22 的**真模型**那批（`ops/vacantrun/possess_pi_real_20260922/`）五格**全部走
    #     PATH shim**：`gateshim.exec_inner` 把 `PI_CODING_AGENT_DIR` 設到這一跑自己的暫存目錄
    #     （自己的 models.json／settings.json、自己的 per-run 掛鉤 extension、自己的 proxy 埠），
    #     **常駐那支 extension 在那五格裡從來沒有被載入**（`cells/*/hook_install.json` 的
    #     `target` 是 `/tmp/vacant-possess/run-pi-*/extensions/vacant.ts`）。
    #   ⇒ 那批是 **shim 這條路**的證據，記在下面的 `SHIM_MEASURED["pi"]`，
    #     **不准拿來點亮本表**（2026-09-22 一度填進來，code review 抓到後撤回）。
    #   ⇒ 本格要等「裝完之後、命令列零個 vacant、pi 載入**常駐** extension、真模型、
    #     常駐 proxyd journal `requests_seen > 0`」量到才准填。
    "pi": "",
    "hermes": "",
}


#: `vacant install` 裝的 **PATH shim（閘門那一側）**這條路，逐個 agent 的**真模型**實測。
#:
#: ⚠ 跟 `CHANNEL_MEASURED` **是兩條路、兩份證據，不可互相背書**：
#:   shim 這條由 `gateshim.exec_inner` 在**這一跑自己的**設定目錄裡起 agent
#:   （pi 是 `PI_CODING_AGENT_DIR`＝暫存目錄），常駐設定檔／常駐 extension **不在路上**。
#:   所以這裡有日期**不代表**常駐通道被證實，`install()` 的 `verified` 只看 `CHANNEL_MEASURED`。
#: ⚠ 反過來也一樣：shim **打完整路徑就繞過**、對 `bash -c` 收不到（`gateshim` 誠實邊界），
#:   這裡的成績**不涵蓋**那些叫法。
#: ⚠ 只收 **L-real**（真 agent、真模型、真流量）；L-fake 不進本表。
#:   本表沒有的 agent ＝**本表沒記**，不是「量過而且失敗」。
SHIM_MEASURED: dict[str, str] = {
    # ✅ `ops/vacantrun/possess_pi_real_20260922/`：Claude Code 遠端容器、pi **0.87.0**、
    #   模型 `gemma-4-12b-it-qat`、上游是人類 LM Studio 的**公開 Tailscale Funnel**
    #   （不是 LAN 直連 1003）。R534 那五題各一格、走 **PATH shim**（命令列零個 vacant，
    #   `pi -p`）：3 交付 exit 0 ／ 2 拒交 exit 20，模型通數 4–13，
    #   五條收據鏈 `--selftest` 先過再驗全 OK，`proven` 由 `requests_seen=7` 點亮。
    #   ⚠ 掛鉤是 shim 當場裝的 **per-run extension** 燒的，不是常駐那支。
    #   ⚠ 沒有 bwrap ⇒ 五格全是 **B′**；互動／長任務／並行**沒量**；n=5 無 rep。
    "pi": "2026-09-22（Claude Code 遠端容器，pi 0.87.0，gemma-4-12b-it-qat，"
          "**上游＝公開 Funnel 非 LAN**，R534 五題走 shim：3 交付／2 拒交，"
          "模型通數 4–13，鏈全 OK，級別 B′；**常駐 extension 不在路上**）",
}


@dataclasses.dataclass(frozen=True)
class AgentSpec:
    """一個 agent 的「常駐設定在哪、怎麼寫、怎麼認得出它裝了」。"""
    name: str
    #: 認「這台機器上有這個 agent」用的目錄（相對 HOME），**存在就算有**。
    config_dirs: tuple[str, ...]
    #: 要寫的那一份設定檔（相對 HOME）。
    config_file: str
    #: 可執行檔名（PATH 探測用；只是補充證據，不是判準）。
    binaries: tuple[str, ...]
    #: 常見安裝位置（PATH 上找不到時掃這裡；相對 HOME 或絕對路徑）。
    bin_hints: tuple[str, ...]
    #: 這個 agent 走哪一條 wire（決定 base url 要不要帶 `/v1`）。
    wire: str
    #: 不該被閘門包起來的子命令／旗標（版本、登入、設定……）。
    passthrough: frozenset[str]
    #: 把整份設定搬走的環境變數（relocate）。`startable` 探測與
    #: `gateshim.exec_inner` 用的是同一個。
    relocate_var: str = ""
    #: 這個 agent 啟動時會去讀的**金鑰環境變數**；`None` ＝ 不需要／用別的方式。
    #: ⚠ 這一格是 2026-09-20 那個洞的根：`codex` 的 `env_key = "OPENAI_API_KEY"`
    #:   在乾淨的 Linux 登入環境裡**沒有值** ⇒ codex 在開任何連線之前就
    #:   `ERROR: Missing environment variable`，而設定檔明明寫好了。
    env_key: str | None = None
    #: **一次性、非互動**的探測命令（`{model}` 會被代換）。
    #: `None` ＝ 這個 agent 沒有已知的一次性叫法 ⇒ `startable` 回 `None`
    #: （**「不量」不是「量到起不來」**，鐵律 3）。
    probe_argv: tuple[str, ...] | None = None


AGENTS: dict[str, AgentSpec] = {
    "claude": AgentSpec(
        name="claude",
        config_dirs=(".claude",),
        config_file=".claude/settings.json",
        binaries=("claude",),
        bin_hints=(".local/bin/claude", ".claude/local/claude",
                   "/opt/homebrew/bin/claude", "/usr/local/bin/claude"),
        wire="anthropic",
        passthrough=frozenset({"--version", "-v", "--help", "-h", "mcp",
                               "config", "update", "doctor", "install",
                               "migrate-installer", "setup-token", "plugin"}),
        relocate_var="CLAUDE_CONFIG_DIR",
        # ⚠ Claude Code 也可以用 OAuth 憑證（`~/.claude/.credentials.json`，
        #   **紅線，本模組不讀**）⇒ 這個變數沒有值**不一定**啟動不了。
        #   所以 `env_key_present=False` 對 claude 不是判決，判決看 `startable`。
        env_key="ANTHROPIC_API_KEY",
        probe_argv=("-p", "ping"),
    ),
    "codex": AgentSpec(
        name="codex",
        config_dirs=(".codex",),
        config_file=".codex/config.toml",
        binaries=("codex",),
        bin_hints=(".local/bin/codex", "/opt/homebrew/bin/codex",
                   "/usr/local/bin/codex"),
        wire="openai",
        passthrough=frozenset({"--version", "-V", "--help", "-h", "login",
                               "logout", "mcp", "completion", "debug",
                               "doctor", "features", "app-server"}),
        relocate_var="CODEX_HOME",
        env_key="OPENAI_API_KEY",
        probe_argv=("exec", "--skip-git-repo-check", "-m", "{model}", "ping"),
    ),
    "opencode": AgentSpec(
        name="opencode",
        config_dirs=(".config/opencode", ".local/share/opencode"),
        config_file=".config/opencode/opencode.json",
        binaries=("opencode",),
        bin_hints=(".opencode/bin/opencode", ".local/bin/opencode",
                   "/opt/homebrew/bin/opencode", "/usr/local/bin/opencode"),
        wire="openai",
        passthrough=frozenset({"--version", "-v", "--help", "-h", "auth",
                               "upgrade", "models", "mcp", "serve"}),
        relocate_var="OPENCODE_CONFIG_DIR",
        # opencode／pi 的設定裡寫得進 `apiKey` 字面值 ⇒ 不吃環境變數
        env_key=None,
        probe_argv=("run", "-m", "vacant/{model}", "ping"),
    ),
    "pi": AgentSpec(
        name="pi",
        config_dirs=(".pi/agent", ".pi"),
        # 2026-09-22 起寫的是 extension，不是 models.json（見 wire_pi）
        config_file=".pi/agent/extensions/vacant.ts",
        binaries=("pi",),
        bin_hints=(".local/bin/pi", ".bun/bin/pi", ".npm-global/bin/pi",
                   "/opt/homebrew/bin/pi", "/usr/local/bin/pi"),
        wire="openai",
        passthrough=frozenset({"--version", "-v", "--help", "-h", "auth",
                               "login", "mcp"}),
        relocate_var="PI_CODING_AGENT_DIR",
        env_key=None,
        probe_argv=("-p", "ping"),
    ),
    "hermes": AgentSpec(
        name="hermes",
        config_dirs=(".hermes",),
        config_file=".hermes/config.yaml",
        binaries=("hermes",),
        bin_hints=(".local/bin/hermes", "/usr/local/bin/hermes"),
        wire="openai",
        passthrough=frozenset({"--version", "-v", "--help", "-h", "model",
                               "auth", "skills"}),
        relocate_var="HERMES_HOME",
        env_key=None,
        # ⚠ **沒有已知的一次性叫法**（Hermes 0.19.0 的非互動入口沒量過）
        #   ⇒ `startable` 回 `None`＝**不量**，不是「起不來」。
        probe_argv=None,
    ),
}

#: `bash -lic` 的輸出會混進終端機的跳脫序列（OSC 7 之類）。**照單全收會拿到
#: 一個不存在的路徑，然後判成「沒裝」**——這台機器上因此誤判過兩次。
_ESC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[A-Za-z]"
                     r"|\x1b[=>]|[\x00-\x08\x0b-\x1f\x7f]")


def strip_terminal_noise(s: str) -> str:
    """把終端機控制序列剝掉，回可以當路徑用的乾淨字串。"""
    return _ESC_RE.sub("", s).strip()


# ── 偵測 ────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Detection:
    agent: str
    #: 設定目錄在不在（**主要判準**）。
    config_dir: str | None
    #: 設定檔在不在。
    config_file_exists: bool
    #: 可執行檔路徑（PATH 或 hint 掃到的）；`None` ＝沒找到，**不等於沒裝**。
    binary: str | None
    #: 怎麼找到那支可執行檔的：`login_shell` / `path` / `hint` / `none`。
    binary_via: str
    version: str | None

    @property
    def present(self) -> bool:
        """這台機器上有沒有這個 agent。**設定目錄或可執行檔，有一個就算有。**"""
        return self.config_dir is not None or self.binary is not None

    def to_json(self) -> dict:
        return {"agent": self.agent, "config_dir": self.config_dir,
                "config_file_exists": self.config_file_exists,
                "binary": self.binary, "binary_via": self.binary_via,
                "version": self.version, "present": self.present}


def _login_shell_which(name: str) -> str | None:
    """用**登入互動 shell** 問 `command -v`。

    ⚠ 非互動 shell 會騙人（使用者的 PATH 多半加在 `~/.zshrc`／`~/.bashrc`
      的互動段），所以要 `-lic`。兩個 shell 都問：`$SHELL` 與 `bash`，
      因為 macOS 預設是 zsh 而 PATH 可能只寫在其中一邊。
    """
    shells = []
    user_shell = os.environ.get("SHELL")
    if user_shell:
        shells.append(user_shell)
    for cand in ("/bin/bash", "bash", "/bin/zsh", "zsh"):
        if cand not in shells:
            shells.append(cand)
    for sh in shells:
        try:
            out = subprocess.run([sh, "-lic", f"command -v {name} 2>/dev/null"],
                                 capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        for line in reversed((out.stdout or "").splitlines()):
            p = strip_terminal_noise(line)
            if p.startswith("/") and os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    return None


def detect_one(spec: AgentSpec, home: pathlib.Path, *,
               probe_shell: bool = True) -> Detection:
    cfg_dir = None
    for d in spec.config_dirs:
        if (home / d).is_dir():
            cfg_dir = str(home / d)
            break
    binary, via = None, "none"
    if probe_shell:
        for b in spec.binaries:
            p = _login_shell_which(b)
            if p:
                binary, via = p, "login_shell"
                break
    if binary is None:
        for b in spec.binaries:
            p = shutil.which(b)
            if p:
                binary, via = p, "path"
                break
    if binary is None:
        for hint in spec.bin_hints:
            p = pathlib.Path(hint) if hint.startswith("/") else home / hint
            if p.is_file() and os.access(p, os.X_OK):
                binary, via = str(p), "hint"
                break
    version = None
    if binary:
        try:
            r = subprocess.run([binary, "--version"], capture_output=True,
                               text=True, timeout=30)
            version = strip_terminal_noise(
                (r.stdout or r.stderr or "").splitlines()[0]) or None
        except (OSError, subprocess.SubprocessError, IndexError):
            version = None
    return Detection(agent=spec.name, config_dir=cfg_dir,
                     config_file_exists=(home / spec.config_file).is_file(),
                     binary=binary, binary_via=via, version=version)


def detect(home: pathlib.Path | None = None, *,
           probe_shell: bool = True) -> dict[str, Detection]:
    h = home or pathlib.Path.home()
    return {n: detect_one(s, h, probe_shell=probe_shell)
            for n, s in AGENTS.items()}


# ── 檔案改動的紀錄 ──────────────────────────────────────────────────────

@dataclasses.dataclass
class FileChange:
    """一次對使用者檔案的改動。**還原需要的資訊全部在這裡。**"""
    path: str
    action: str                 # "create" | "modify"
    before_sha256: str | None   # create ⇒ None
    after_sha256: str
    backup: str | None          # modify ⇒ 備份檔路徑
    note: str = ""

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _assert_not_credential(home: pathlib.Path, p: pathlib.Path) -> None:
    try:
        rel = p.resolve().relative_to(home.resolve()).as_posix()
    except ValueError:
        rel = ""
    if rel in NEVER_TOUCH:
        raise PermissionError(f"紅線：{rel} 是憑證，本模組不讀不寫")


def write_tracked(home: pathlib.Path, path: pathlib.Path, data: bytes,
                  backups: pathlib.Path, note: str = "") -> FileChange:
    """寫一個檔案，並且**把還原需要的東西一起落下來**。"""
    _assert_not_credential(home, path)
    existed = path.is_file()
    before = sha256_file(path) if existed else None
    backup_path = None
    if existed:
        backups.mkdir(parents=True, exist_ok=True)
        # 備份檔名帶 sha256 前綴：同一個檔被改兩次也不會互相蓋掉
        backup_path = backups / f"{path.name}.{before[:12]}.bak"
        shutil.copy2(path, backup_path)
        if sha256_file(backup_path) != before:
            raise RuntimeError(f"備份沒複製對：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return FileChange(path=str(path), action="modify" if existed else "create",
                      before_sha256=before, after_sha256=sha256_file(path),
                      backup=str(backup_path) if backup_path else None,
                      note=note)


# ── 通道層：逐個 agent 把 base url 寫進它自己的常駐設定檔 ────────────────

BEGIN_MARK = "# >>> vacant possess >>>"
END_MARK = "# <<< vacant possess <<<"
PROVIDER_ID = "vacant"


def _base_for(wire: str, port: int) -> str:
    root = f"http://127.0.0.1:{port}"
    return root + ("/v1" if wire == "openai" else "")


def wire_claude(home: pathlib.Path, port: int, backups: pathlib.Path,
                **_: Any) -> list[FileChange]:
    """`~/.claude/settings.json` 的 `env` 區塊。

    ⚠ 只加 `ANTHROPIC_BASE_URL` 一個 key，**不碰 `ANTHROPIC_API_KEY`**
      （憑證紅線），其餘欄位逐位元保留。
    """
    p = home / AGENTS["claude"].config_file
    doc = json.loads(p.read_text("utf-8")) if p.is_file() else {}
    if not isinstance(doc, dict):
        raise RuntimeError(f"{p} 不是 JSON 物件，不動它")
    env = dict(doc.get("env") or {})
    env["ANTHROPIC_BASE_URL"] = _base_for("anthropic", port)
    doc["env"] = env
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    return [write_tracked(home, p, data, backups,
                          note="env.ANTHROPIC_BASE_URL")]


def wire_opencode(home: pathlib.Path, port: int, backups: pathlib.Path,
                  **_: Any) -> list[FileChange]:
    """`~/.config/opencode/opencode.json`。

    做兩件事：
      · 把**已經存在的每一個 provider** 的 `options.baseURL` 改指向 proxy
        （使用者實際在用的那幾條路才是重點）；
      · 另外加一個 `vacant` provider，讓「指到本地模型」也有路可走。

    ⚠ 沒有動頂層 `model`：那是使用者選的模型，換掉它等於替人做決定。
      代價是**使用者如果選了一個沒被我們改道的 provider，那條路沒被中介**
      ——`install-status` 會把有幾個 provider 被改道印出來。
    """
    p = home / AGENTS["opencode"].config_file
    doc = json.loads(p.read_text("utf-8")) if p.is_file() else {}
    if not isinstance(doc, dict):
        raise RuntimeError(f"{p} 不是 JSON 物件，不動它")
    base = _base_for("openai", port)
    providers = dict(doc.get("provider") or {})
    touched = []
    for pid, pv in list(providers.items()):
        if not isinstance(pv, dict):
            continue
        opts = dict(pv.get("options") or {})
        opts["baseURL"] = base
        pv = dict(pv)
        pv["options"] = opts
        providers[pid] = pv
        touched.append(pid)
    # 內建雲端 provider：使用者沒在設定裡列出來也要蓋掉，否則那條路直連
    for pid in ("openai", "anthropic"):
        pv = dict(providers.get(pid) or {})
        opts = dict(pv.get("options") or {})
        opts["baseURL"] = (base if pid == "openai"
                           else _base_for("anthropic", port))
        pv["options"] = opts
        providers[pid] = pv
        if pid not in touched:
            touched.append(pid)
    # 再加一個**可以直接用**的 provider：改道既有 provider 只讓原本的模型換路，
    # 使用者要指到本地模型仍然需要一個自訂 provider
    # （`envmap.CONFIG_ROUTE["opencode"]`：內建 provider 只吃 models.dev 的 id）。
    model = os.environ.get("VACANT_AGENT_MODEL", "gemma-4-12b-it-qat")
    providers[PROVIDER_ID] = {
        "name": "vacant possess", "npm": "@ai-sdk/openai-compatible",
        "options": {"baseURL": base, "apiKey": "sk-vacant-possess"},
        "models": {model: {"name": model}},
    }
    touched.append(PROVIDER_ID)
    doc["provider"] = providers
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    return [write_tracked(home, p, data, backups,
                          note=f"provider.*.options.baseURL ×{len(touched)}"
                               f"（{','.join(touched)}）")]


#: Codex 的沙箱姿態預設值。**這是白拿的一層**：`workspace-write` 是 codex
#: 自己實作的限制，它**不給 shell 指令網路**——比我們的 `PATH` shim 強，
#: 因為它擋的是「agent 用 shell 工具直接 `curl` 模型端點」那條路（C 類洞），
#: 而那條路上 wire 是零紀錄、收據卻照樣 `accepted=true`。
#: ⚠ **這不是「擋得住」**：codex 自己可以被旗標覆寫，而且本 repo 的實驗
#:   harness（`ops/vacantrun/wrap_agent.sh`）就是刻意全開的。
#:   能說的只有「產品這一側的預設不再是自己把牆拆掉」。
CODEX_SANDBOX_DEFAULT = "workspace-write"

#: 把 agent 自己的防護關掉的旗標。⚠ **這是「我們認得出來的那些」，不是全部**
#: （鐵律 3：名單沒命中不等於沒有人拆牆）。
DANGER_FLAGS: dict[str, tuple[str, ...]] = {
    "codex": ("--dangerously-bypass-approvals-and-sandbox", "--yolo",
              "--full-auto"),
    "claude": ("--dangerously-skip-permissions",),
    "hermes": ("--yolo",),
    "opencode": (),
    "pi": (),
}


def codex_sandbox_choice() -> str | None:
    """`install` 要把 codex 的 `sandbox_mode` 釘成什麼。

    `VACANT_POSSESS_CODEX_SANDBOX` 可以覆寫；`keep`／空字串 ⇒ **不碰**
    （維持使用者原本的姿態）。⚠ **覆寫會留痕**：值會進 `state`、進
    `install-status` 的 `agent_posture`，而且只要不是預設值就會進 `warnings`。
    """
    v = os.environ.get("VACANT_POSSESS_CODEX_SANDBOX")
    if v is None:
        return CODEX_SANDBOX_DEFAULT
    v = v.strip()
    if v in ("", "keep", "none"):
        return None
    return v


def read_agent_posture(home: pathlib.Path, agent: str) -> dict:
    """把這個 agent **現在的**沙箱／approval 姿態讀出來。

    存在的理由（Fable 2026-09-20）：一個在 `workspace-write` 底下跑出來的
    `accepted=true`，跟一個在 `danger-full-access` 底下跑出來的 `accepted=true`，
    **收據上長得一模一樣**。那正是 A 類那四格的病——真拒交與假拒交只差一個
    沒被記下來的欄位。

    ⚠ **讀不出來一律 `None`，不准寫空字串**（鐵律 3：沒量到 ≠ 量到 0）。
      `None` 的意思是「這一格我們沒有量到」，不是「這個 agent 沒有沙箱」。
    """
    out: dict[str, Any] = {"agent": agent, "sandbox_mode": None,
                           "approval_policy": None, "flags": None,
                           "source": None, "measured": False}
    spec = AGENTS.get(agent)
    if spec is None:
        return out
    p = home / spec.config_file
    out["source"] = str(p)
    if not p.is_file():
        out["note"] = "設定檔不存在 ⇒ 沒量到（不是「沒有沙箱」）"
        return out
    if agent == "codex":
        try:
            import tomllib
            doc = tomllib.loads(p.read_text("utf-8"))
        except (OSError, ValueError, Exception):
            out["note"] = "config.toml 解析不了 ⇒ 沒量到"
            return out
        out.update(sandbox_mode=doc.get("sandbox_mode"),
                   approval_policy=doc.get("approval_policy"), measured=True)
        return out
    if agent == "claude":
        try:
            doc = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            out["note"] = "settings.json 解析不了 ⇒ 沒量到"
            return out
        perm = doc.get("permissions") or {}
        out.update(approval_policy=perm.get("defaultMode"), measured=True,
                   note="⚠ Claude Code 沒有 codex 那種 `sandbox_mode` 欄位；"
                        "這裡量的是 `permissions.defaultMode`，"
                        "`--dangerously-skip-permissions` 是**命令列**旗標，"
                        "要看 `flags`（那一格由 shim 逐跑記）")
        return out
    out["note"] = ("這個 agent 的沙箱姿態我們沒有已知的讀法 ⇒ 沒量到"
                   "（不是「沒有沙箱」）")
    return out


def posture_from_argv(agent: str, argv: Iterable[str]) -> list[str]:
    """這一次呼叫的命令列上有哪些**我們認得出來的**拆牆旗標。"""
    known = DANGER_FLAGS.get(agent, ())
    seen = set(argv)
    return [f for f in known if f in seen]


_TOP_KEY_RE = re.compile(r"^\s*model_provider\s*=")
_SANDBOX_RE = re.compile(r"^\s*sandbox_mode\s*=")


def wire_codex(home: pathlib.Path, port: int, backups: pathlib.Path,
               **_: Any) -> list[FileChange]:
    """`~/.codex/config.toml`：加一個**新** provider id 並把 `model_provider`
    指過去。

    ⚠ 內建 id `openai` 不准覆寫（codex 會 fail-closed 報錯），所以叫 `vacant`。
    ⚠ `wire_api` 在 0.147.0 上只收 `"responses"`（`envmap.CONFIG_ROUTE["codex"]`）。
    ⚠ **這條路救不了 `codex login`（ChatGPT 帳號）**：那條的模型通道是寫死的
      `wss://chatgpt.com/...`，設定搬不動（`envmap` 誠實邊界 4）。
      也就是說**裝了之後，走 ChatGPT 登入的那條路仍然沒有被中介**。

    ## 順手釘一層**不是我們實作的**防護：`sandbox_mode`

    codex 的預設沙箱 `workspace-write` **本來就不給 shell 指令網路**。
    `install` 以前對沙箱姿態完全無作為，等於把一層白拿的防護放著不用——而
    最致命的那一類洞（agent 用 shell 工具直接 `curl` 模型端點，wire 零紀錄
    但收據 `accepted=true`）**有一半是「牆被拆掉」造成的**。所以這裡把它
    釘回 `workspace-write`。

    ⚠ **這不是「擋得住」**：codex 自己的旗標可以覆寫它，我們也留了
      `VACANT_POSSESS_CODEX_SANDBOX` 這個逃生口——**但覆寫會留痕**
      （`state` 的 `agent_posture` ＋ `install` 的 `warnings`）。
    ⚠ **原值整份備份、`uninstall` 逐位元還原**：不准留下一個裝上去就拔不掉
      的東西。原值也寫在同一行的標記註解裡，肉眼看得到。
    ⚠ 本 repo 的實驗 harness（`ops/vacantrun/wrap_agent.sh`）**刻意全開**，
      那是 harness 不是產品，這裡不碰它。
    """
    p = home / AGENTS["codex"].config_file
    text = p.read_text("utf-8") if p.is_file() else ""
    # 先把上一次留下的區塊整個拿掉（重裝要冪等）
    text = _strip_block(text)
    lines = text.splitlines()
    sandbox = codex_sandbox_choice()
    out, replaced, sb_done = [], False, (sandbox is None)
    for ln in lines:
        if _TOP_KEY_RE.match(ln) and not replaced:
            out.append(f'model_provider = "{PROVIDER_ID}"   '
                       f'{BEGIN_MARK} 原值：{ln.strip()} {END_MARK}')
            replaced = True
        elif _SANDBOX_RE.match(ln) and not sb_done:
            out.append(f'sandbox_mode = "{sandbox}"   '
                       f'{BEGIN_MARK} 原值：{ln.strip()} {END_MARK}')
            sb_done = True
        else:
            out.append(ln)
    if not replaced:
        # 頂層 key 一定要在第一個 table header 之前
        insert_at = next((i for i, ln in enumerate(out)
                          if ln.lstrip().startswith("[")), len(out))
        out.insert(insert_at,
                   f'model_provider = "{PROVIDER_ID}"   {BEGIN_MARK}'
                   f' 原本沒有這個 key {END_MARK}')
    if not sb_done:
        insert_at = next((i for i, ln in enumerate(out)
                          if ln.lstrip().startswith("[")), len(out))
        out.insert(insert_at,
                   f'sandbox_mode = "{sandbox}"   {BEGIN_MARK}'
                   f' 原本沒有這個 key（codex 預設就是 workspace-write）'
                   f' {END_MARK}')
    block = [
        "", BEGIN_MARK,
        f"[model_providers.{PROVIDER_ID}]",
        'name = "vacant possess proxy"',
        f'base_url = "{_base_for("openai", port)}"',
        'wire_api = "responses"',
        'env_key = "OPENAI_API_KEY"',
        END_MARK, "",
    ]
    data = ("\n".join(out).rstrip("\n") + "\n" + "\n".join(block)).encode()
    # 自己驗一次語法：寫壞 config.toml ⇒ codex 連載入都失敗
    try:
        import tomllib
        tomllib.loads(data.decode("utf-8"))
    except Exception as e:                      # pragma: no cover - 防呆
        raise RuntimeError(f"產出的 config.toml 解析不了，不寫：{e}") from e
    note = f"model_provider + [model_providers.{PROVIDER_ID}]"
    note += (f" + sandbox_mode={sandbox!r}" if sandbox
             else " + sandbox_mode **沒碰**（VACANT_POSSESS_CODEX_SANDBOX=keep）")
    return [write_tracked(home, p, data, backups, note=note)]


def wire_pi(home: pathlib.Path, port: int, backups: pathlib.Path,
            python: str | None = None, models: list[str] | None = None,
            **_: Any) -> list[FileChange]:
    """`~/.pi/agent/extensions/vacant.ts`——**一支 extension，不碰 `models.json`**。

    2026-09-22 之前這裡改寫 `models.json`（每個 provider 的 `baseUrl` 全部改道＋加一個
    `vacant` provider）。那一格從來沒有被 `requests_seen` 證實過，而且從 pi 0.87.0 原始碼
    讀到 `models-store.json` 只是目錄快取、`models.json` 才是設定之後，發現根本不必寫它：
    extension 在 runtime `pi.registerProvider()`、`pi.setModel()`、`pi.registerCommand("vacant")`
    就把通道、預設開、`/vacant on|off|status`、掛鉤七事件全部做完（`piext.py` 的 docstring）。

    ⚠ 使用者自己的 provider **一個都不改道**：`/vacant off` 或 `/model` 切走就是不經過
      Vacant，extension 會留一筆 `vacant_off`，收據不替它說謊（`piext` 誠實邊界 3）。
    ⚠ `CHANNEL_MEASURED["pi"]` 仍是空字串：**這支常駐 extension 只有 L-fake**
      （`ops/vacantrun/possess_pi_20260922/`，假上游）。2026-09-22 的真模型那批
      （`possess_pi_real_20260922/`）五格全走 PATH shim——shim 把 `PI_CODING_AGENT_DIR`
      搬到這一跑自己的暫存目錄，**本函式寫的這支檔在那裡不會被載入**——所以那批只記進
      `SHIM_MEASURED["pi"]`，不准拿來填本格。要用真模型、命令列零個 vacant、常駐 proxyd
      journal `requests_seen > 0` 量到**這支**被載入才准填。
    ⚠ agent 刪得掉這支檔（實測）。刪掉 ⇒ 下一跑 canary 不燒 ⇒ 收據降級，不是保證。
    """
    from . import piext
    p = home / AGENTS["pi"].config_file
    body = piext.render(port=port, state_dir=str(state_home(home)),
                        python=python or sys.executable,
                        package_path=package_path(), models=models or [])
    return [write_tracked(home, p, body.encode("utf-8"), backups,
                          note="pi extension：registerProvider(vacant) + /vacant + 掛鉤")]


def wire_hermes(home: pathlib.Path, port: int, backups: pathlib.Path,
                **_: Any) -> list[FileChange]:
    """`~/.hermes/config.yaml`：`model.provider: custom` ＋ `model.base_url`。

    ⚠ **兩行缺一不可**：只有 base_url 沒有 provider ⇒ Hermes 0.19.0 停在
      `No LLM provider configured`，`requests_seen == 0`
      （`envmap.CONFIG_ROUTE["hermes"]` 的實測）。
    ⚠ 這裡用**行導向**編輯而不是 YAML 函式庫（runtime 依賴只有 `cryptography`）。
      原檔整份備份，`uninstall` 逐位元還原。
    """
    p = home / AGENTS["hermes"].config_file
    text = _strip_block(p.read_text("utf-8")) if p.is_file() else ""
    base = _base_for("openai", port)
    ctx = os.environ.get("VACANT_HERMES_CONTEXT", "65536")
    lines = text.splitlines()
    out: list[str] = []
    in_model = False
    seen_model = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("model:") and not ln.startswith((" ", "\t")):
            in_model, seen_model = True, True
            out.append(ln)
            out.append(f"  provider: custom   {BEGIN_MARK}")
            out.append(f"  base_url: {base}")
            out.append(f"  context_length: {ctx}   {END_MARK}")
            continue
        if in_model and ln and not ln.startswith((" ", "\t")):
            in_model = False
        if in_model and re.match(r"\s*(provider|base_url|context_length)\s*:", ln):
            continue                    # 原本那幾行讓位給我們的
        out.append(ln)
    if not seen_model:
        out += ["", BEGIN_MARK, "model:", "  provider: custom",
                f"  base_url: {base}", f"  context_length: {ctx}", END_MARK]
    data = ("\n".join(out).strip("\n") + "\n").encode()
    return [write_tracked(home, p, data, backups,
                          note="model.provider=custom + model.base_url")]


def _strip_block(text: str) -> str:
    """把上一次留下的 `>>> vacant possess >>>` 區塊整段拿掉（重裝要冪等）。"""
    if BEGIN_MARK not in text:
        return text
    out, skipping = [], False
    for ln in text.splitlines():
        if BEGIN_MARK in ln and END_MARK in ln:
            continue                    # 單行標記（codex 的 model_provider）
        if BEGIN_MARK in ln:
            skipping = True
            continue
        if END_MARK in ln:
            skipping = False
            continue
        if not skipping:
            out.append(ln)
    return "\n".join(out)


WIRERS: dict[str, Callable[..., list[FileChange]]] = {
    "claude": wire_claude,
    "codex": wire_codex,
    "opencode": wire_opencode,
    "pi": wire_pi,
    "hermes": wire_hermes,
}


# ── 上游來源（裝之前先記下來使用者本來指到哪） ──────────────────────────

def discover_install_upstreams(home: pathlib.Path,
                               overrides: dict[str, str] | None = None
                               ) -> dict[str, dict]:
    """常駐 proxy 要轉去哪。**先讀使用者現在的設定，再讀環境變數。**

    找不到 ⇒ `envmap.SINK_UPSTREAM`（fail-closed：開連線之前就 502），
    **不是**公開 API。理由同 `envmap.SINK_UPSTREAM` 的 docstring。
    """
    found: dict[str, dict] = {}
    ov = overrides or {}
    for wire in ("openai", "anthropic"):
        if wire in ov:
            found[wire] = {"url": ov[wire], "source": "--upstream"}
            continue
        url, src = None, None
        for _w, names in envmap.UPSTREAM_VARS:
            if _w != wire:
                continue
            for n in names:
                v = os.environ.get(n)
                if v:
                    url, src = v, f"env:{n}"
                    break
        if url is None:
            url, src = _scan_configs_for_upstream(home, wire)
        if url is None:
            url, src = envmap.SINK_UPSTREAM, "sink（沒有人指定）"
        found[wire] = {"url": url, "source": src}
    return found


def _scan_configs_for_upstream(home: pathlib.Path,
                               wire: str) -> tuple[str | None, str | None]:
    """從使用者**現有**的 agent 設定裡挖出他本來指到哪。

    ⚠ 只讀設定檔，**不讀任何 auth/憑證檔**。
    """
    if wire == "openai":
        p = home / AGENTS["opencode"].config_file
        if p.is_file():
            try:
                doc = json.loads(p.read_text("utf-8"))
                for pid, pv in (doc.get("provider") or {}).items():
                    url = ((pv or {}).get("options") or {}).get("baseURL")
                    if url and "127.0.0.1" not in url and "localhost" not in url:
                        return str(url), f"opencode:provider.{pid}"
            except (OSError, ValueError):
                pass
        p = home / AGENTS["codex"].config_file
        if p.is_file():
            try:
                import tomllib
                doc = tomllib.loads(p.read_text("utf-8"))
                for pid, pv in (doc.get("model_providers") or {}).items():
                    url = (pv or {}).get("base_url")
                    if url and "127.0.0.1" not in url and "localhost" not in url:
                        return str(url), f"codex:model_providers.{pid}"
            except (OSError, ValueError, Exception):
                pass
    else:
        p = home / AGENTS["claude"].config_file
        if p.is_file():
            try:
                doc = json.loads(p.read_text("utf-8"))
                url = (doc.get("env") or {}).get("ANTHROPIC_BASE_URL")
                if url and "127.0.0.1" not in url:
                    return str(url), "claude:env.ANTHROPIC_BASE_URL"
            except (OSError, ValueError):
                pass
    return None, None


# ── 閘門層：PATH shim ───────────────────────────────────────────────────

SHIM_TEMPLATE = """#!/bin/sh
# vacant possess shim — 閘門層。
# ⚠ **打完整路徑就跳過這支。** 這一層做得到「預設會跑」，做不到「不會被繞過」。
VACANT_POSSESS_SHIM_DIR={shim_dir}
export VACANT_POSSESS_SHIM_DIR
# ⚠ 這一行讓 shim **自己帶得動套件**：使用者的 shell 沒有 PYTHONPATH，
#   而原始碼 checkout（沒 pip install）底下 `import vacant_network` 會失敗。
#   已經 pip install 的情況下這一條是多餘但無害的。
PYTHONPATH={pypath}${{PYTHONPATH:+:$PYTHONPATH}}
export PYTHONPATH
exec {python} -m vacant_network.vrun.gateshim {agent} "$@"
"""


def install_shims(state: pathlib.Path, agents: Iterable[str],
                  python: str) -> tuple[pathlib.Path, list[str]]:
    shim_dir = state / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for a in agents:
        p = shim_dir / a
        p.write_text(SHIM_TEMPLATE.format(
            shim_dir=_sh_quote(str(shim_dir)), python=_sh_quote(python),
            pypath=_sh_quote(package_path()), agent=a), encoding="utf-8")
        p.chmod(0o755)
        made.append(str(p))
    return shim_dir, made


def _sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


RC_FILES = ("~/.zshrc", "~/.bashrc", "~/.bash_profile", "~/.profile")

#: `~/.bashrc` 裡「非互動就 return」那一段的幾種常見寫法。
#: Ubuntu 24.04 的 stock `.bashrc` 是第一種，**第 6 行就 `return`**。
_NONINTERACTIVE_GUARDS = (
    re.compile(r"^\s*case\s+\$-\s+in"),                 # case $- in *i*) ;; *) return
    re.compile(r"^\s*\[\s+-z\s+[\"']?\$PS1"),           # [ -z "$PS1" ] && return
    re.compile(r"^\s*\[\[\s+\$-\s*!=\s*\*i\*"),         # [[ $- != *i* ]] && return
)


def _noninteractive_guard_at(text: str) -> int | None:
    """`~/.bashrc` 那一段「非互動就 return」從第幾行開始。找不到回 `None`。

    ⚠ 只認**後面 6 行內真的有 `return`** 的那一段，免得把一個剛好長得像的
      `case` 當成守衛，然後把 PATH 區塊插到一個奇怪的地方。
    """
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if not any(g.match(ln) for g in _NONINTERACTIVE_GUARDS):
            continue
        if any(re.search(r"\breturn\b", x) for x in lines[i:i + 6]):
            return i
    return None


def _path_block(shim_dir: pathlib.Path) -> str:
    """PATH 區塊的內容。**冪等**：已經在 PATH 上就不再加一次。

    ⚠ 2026-09-20 在 vacant-dev 上量到的 bug：`.profile` 與 `.bashrc` **兩個都
      被加了**，而 `bash -lic` 兩個都會 source ⇒ **shim 目錄在 PATH 上出現兩次**。
      開一次終端機加一次，會累積。`case` 這個守衛讓它加幾次都只有一份。
    """
    q = _sh_quote(str(shim_dir))
    return (f"\n{BEGIN_MARK}\n"
            f"# 閘門層：把 shim 目錄放到 PATH 前面。**打完整路徑就跳過。**\n"
            f"# ⚠ 這個區塊只在**會 source 這個檔**的 shell 裡生效；\n"
            f"#   `bash -c`（非登入非互動）不讀任何 rc 檔 ⇒ 那條路上沒有閘門。\n"
            f"case \":$PATH:\" in\n"
            f"  *\":{str(shim_dir)}:\"*) ;;\n"
            f"  *) PATH={q}:\"$PATH\" ; export PATH ;;\n"
            f"esac\n"
            f"{END_MARK}\n")


def install_path_block(home: pathlib.Path, shim_dir: pathlib.Path,
                       backups: pathlib.Path) -> list[FileChange]:
    """把 shim 目錄加到 `PATH` 前面，寫進使用者的 shell rc。

    ⚠ 這是本模組唯一會動 shell 設定的地方，而且是一個**有頭有尾的區塊**
      （`>>> vacant possess >>>` … `<<< vacant possess <<<`），`uninstall`
      只拿掉這一段，其餘逐位元不動。

    ## 兩個 2026-09-20 在 Linux 上量出來的問題，這一支各修一半

    1. **PATH 出現兩次**（`.profile` 與 `.bashrc` 都加，`bash -lic` 兩個都讀）
       ⇒ 區塊改成 `case` 守衛，**加幾次都只有一份**（`_path_block`）。
    2. **非互動 shell 收不到**：Ubuntu stock `~/.bashrc` 第 6 行就
       `case $- in *i*) ;; *) return;; esac`，而舊版是把區塊**附加在檔尾**
       ⇒ `ssh 主機 '指令'`（sshd 起的 bash **會** source `.bashrc`）整段跑不到。
       ⇒ 現在 `.bashrc` 的區塊插在**那個 return 之前**。

    ⚠ **這一支修不掉 `bash -c`（非登入非互動）。** 那種 shell **一個 rc 檔都不讀**
      （除非 `BASH_ENV` 已經在環境裡，而要設 `BASH_ENV` 本身就需要一個
      已經生效的環境——雞生蛋）。`systemd --user` 那一類另外靠
      `install_systemd_path_env()`。剩下的部分**由 `probe_gate_reach()` 當場量、
      `install` 收尾直接警告、`status` 長期印出來**——不准安靜地只覆蓋一半。
    """
    changes = []
    block = _path_block(shim_dir)
    for rc in RC_FILES:
        p = pathlib.Path(rc.replace("~", str(home)))
        if not p.is_file():
            continue
        text = p.read_text("utf-8")
        if BEGIN_MARK in text:
            text = _strip_block(text)
        note = "PATH 前置 shim 目錄（冪等 case 守衛）"
        at = _noninteractive_guard_at(text) if p.name == ".bashrc" else None
        if at is not None:
            lines = text.splitlines()
            body = ("\n".join(lines[:at]) + block + "\n".join(lines[at:]))
            note += "；**插在非互動 return 之前**（ssh 主機 '指令' 才收得到）"
        else:
            body = text.rstrip("\n") + "\n" + block
        changes.append(write_tracked(home, p, body.encode(), backups,
                                     note=note))
    return changes


#: `systemd --user` 起的 unit 的環境來源。**這是無人值守迴圈那一條路。**
SYSTEMD_ENV_FILE = ".config/environment.d/50-vacant-possess.conf"


def install_systemd_path_env(home: pathlib.Path, shim_dir: pathlib.Path,
                             backups: pathlib.Path, *,
                             apply_now: bool = False) -> dict:
    """把 shim 目錄寫進 `~/.config/environment.d/`，給 `systemd --user` 的 unit。

    展場的無人值守迴圈多半是一個 `systemd --user` unit 或一行 `bash -c`，
    **那兩條都讀不到 shell rc**。這一支處理前者。

    ⚠ **寫了檔不等於立刻生效**：`environment.d` 是 user manager **啟動時**
      讀的，已經在跑的那個 manager 不會重讀。兩條路：
        · 等下一次 user manager 啟動（重開機／登出到零 session 再登入）；
        · `--systemd-path-now` ⇒ 另外對**正在跑的** manager 下
          `systemctl --user set-environment PATH=…`。
    ⚠ `--systemd-path-now` 預設是關的，因為它動的是一個**共用的** user manager
      （那台機器上還有別人的 unit，例如 vacant-dev 的 `vacant-exhibit.service`）。
      它只影響**之後才啟動**的 unit，已經在跑的不受影響；`uninstall` 會把
      manager 的 `PATH` 設回原值（原本沒有這個變數 ⇒ `unset-environment`，
      unit 就回到 manager 內建的預設 PATH）。
    ⚠ 生效與否**不猜**：`probe_gate_reach()` 用 `systemd-run --user` 當場量。
    """
    rep: dict[str, Any] = {"file": None, "applied_now": False, "changes": []}
    if platform.system() != "Linux":
        rep["skipped"] = "非 Linux"
        return rep
    p = home / SYSTEMD_ENV_FILE
    body = (f"# {BEGIN_MARK}\n"
            f"# vacant possess：給 systemd --user 起的 unit 用的 PATH。\n"
            f"# ⚠ user manager **啟動時**才讀這個檔。\n"
            f"PATH={shim_dir}:${{PATH}}\n").encode()
    ch = write_tracked(home, p, body, backups,
                       note="systemd --user 的 PATH（environment.d）")
    rep["file"] = str(p)
    rep["changes"] = [ch.to_json()]
    if apply_now and shutil.which("systemctl"):
        before = _systemd_manager_path()
        rep["manager_path_before"] = before
        # ⚠ `before is None` ⇒ manager 的 `show-environment` 裡本來就沒有
        #   `PATH`（unit 吃的是內建預設）。這時候**不可以**只設成 shim 目錄
        #   ——那會讓之後啟動的每一個 unit 失去 `/usr/bin`。補一份保守的預設。
        newp = (f"{shim_dir}:{before}" if before else
                f"{shim_dir}:/usr/local/bin:/usr/bin:/bin:"
                f"/usr/local/sbin:/usr/sbin:/sbin")
        rep["manager_path_after"] = newp
        r = subprocess.run(["systemctl", "--user", "set-environment",
                            f"PATH={newp}"], capture_output=True, text=True)
        rep["applied_now"] = r.returncode == 0
        rep["rc"] = r.returncode
        rep["stderr"] = (r.stderr or "")[:200]
    return rep


def _systemd_manager_path() -> str | None:
    """正在跑的 `systemd --user` manager 目前的 `PATH`；沒有就回 `None`。"""
    if not shutil.which("systemctl"):
        return None
    try:
        r = subprocess.run(["systemctl", "--user", "show-environment"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    for ln in (r.stdout or "").splitlines():
        if ln.startswith("PATH="):
            return ln[5:]
    return None


def restore_systemd_path_env(svc_env: dict) -> dict:
    """把 `--systemd-path-now` 動過的 manager `PATH` 設回去。

    ⚠ 原本 `show-environment` 裡**沒有** `PATH` ⇒ `unset-environment PATH`，
      unit 就回到 manager 內建的預設值——那正是我們動它之前的狀態。
    """
    rep: dict[str, Any] = {"action": "skipped"}
    if not (svc_env or {}).get("applied_now"):
        rep["reason"] = "沒有對正在跑的 manager 動過 ⇒ 不動"
        return rep
    if not shutil.which("systemctl"):       # pragma: no cover
        rep["reason"] = "沒有 systemctl"
        return rep
    before = svc_env.get("manager_path_before")
    if before:
        r = subprocess.run(["systemctl", "--user", "set-environment",
                            f"PATH={before}"], capture_output=True, text=True)
        rep.update(action="restored", rc=r.returncode, to=before)
    else:
        r = subprocess.run(["systemctl", "--user", "unset-environment", "PATH"],
                           capture_output=True, text=True)
        rep.update(action="unset", rc=r.returncode,
                   note="原本就沒有 PATH ⇒ 回到 manager 內建預設")
    rep["stderr"] = (r.stderr or "")[:200]
    return rep


# ── `startable`：這個 agent 在這台機器上**真的起得來嗎** ───────────────

class _ProbeListener:
    """一個一次性的本機 listener：**只記「有沒有人連進來」，不轉送任何東西**。

    這是 `startable` 探測不打模型的關鍵——agent 以為它在連一個 OpenAI／
    Anthropic 端點，實際上另一頭是這支，收到連線就記一筆、回一個 503 然後關掉。
    **零 token、零費用、零外網**（127.0.0.1，而且不解 DNS、不開任何 upstream）。
    """

    def __init__(self) -> None:
        import socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.connections = 0
        self.first_line = ""
        self._stop = False
        self._th = None

    def start(self) -> None:
        import threading
        self._th = threading.Thread(target=self._serve, daemon=True)
        self._th.start()

    def _serve(self) -> None:
        body = (b'{"error":{"type":"vacant_startable_probe",'
                b'"message":"startable probe: no model was called"}}')
        while not self._stop:
            try:
                self.sock.settimeout(0.5)
                conn, _ = self.sock.accept()
            except OSError:
                continue
            self.connections += 1
            try:
                conn.settimeout(1.0)
                data = conn.recv(4096)
                if not self.first_line:
                    self.first_line = data.split(b"\r\n", 1)[0].decode(
                        "utf-8", "replace")[:200]
                conn.sendall(b"HTTP/1.1 503 Service Unavailable\r\n"
                             b"Content-Type: application/json\r\n"
                             b"Content-Length: " + str(len(body)).encode() +
                             b"\r\nConnection: close\r\n\r\n" + body)
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def close(self) -> None:
        self._stop = True
        try:
            self.sock.close()
        except OSError:
            pass


def probe_startable(agent: str, *, home: pathlib.Path | None = None,
                    binary: str | None = None, timeout_s: float = 20.0,
                    model: str | None = None) -> dict:
    """**真的把這個 agent 跑起來一次**，看它能不能走到「開連線」那一步。

    2026-09-20 在 vacant-dev 上量到的洞：`install-status` 說「✓ 已寫入」，
    而 codex 因為登入環境沒有 `OPENAI_API_KEY`，在**開任何連線之前**就
    `ERROR: Missing environment variable` ⇒ 那個 agent 完全用不了。
    **「設定檔寫好了」不等於「那個 agent 跑得起來」**，所以要有這一欄。

    ## 怎麼做到「真的跑一次」又「不打模型」

      1. 開一個 `_ProbeListener`（127.0.0.1，隨機埠），它**只收連線不轉送**；
      2. 用**跟 `install` 寫出來的同一份設定**（同一支 `WIRERS[agent]`）寫進一個
         暫時的 HOME，只是 base url 指向那個 listener；
      3. 用 `relocate_var` 把 agent 的設定搬到那份暫時的 HOME，**不動使用者
         自己那一份**，也**不塞任何金鑰**（塞了就量不到這個洞）；
      4. 跑一次 `probe_argv`，硬性 timeout 後 kill。

    **判準＝listener 有沒有收到連線。** 有 ⇒ 這個 agent 在這台機器上、
    用這份設定、用**現在這個環境**，起得來並且開得了連線。

    ## ⚠ 這個探測量不到什麼（改碼請保留）

      · **量不到「跑得完一題」。** 它停在「第一個 byte 出門」，模型回什麼、
        agent 後面會不會壞掉、驗收會不會過，**一律不在範圍內**。
      · **量不到使用者那份常駐設定檔本身有沒有寫錯。** 它用的是 relocate 的
        複本（同一支 wirer、同一個 `env_key`），所以它答得出「這份設定的形狀
        ＋ 這台機器的環境」行不行，答不出「`~/.codex/config.toml` 現在的內容
        有沒有被人改壞」——那一格看 `files[*].changed_since_install`。
      · **量不到通道有沒有真的被中介。** 那是 `proven`（`requests_seen > 0`），
        兩欄不可混講（`envmap` 誠實邊界 1）。
      · **`startable: None` ＝ 沒量到，不是起不來**（鐵律 3）：沒有可執行檔
        （L-none）、沒有已知的一次性叫法（hermes）都會落在這一格。
      · 探測用的 prompt 送不到模型，但 agent **可能**在連上之前先做別的事
        （更新檢查、MCP 啟動）。那些也算「起得來」——本欄問的就是這個。
    """
    h = (home or pathlib.Path.home()).expanduser()
    spec = AGENTS[agent]
    key = spec.env_key
    key_present = bool(os.environ.get(key)) if key else None
    out: dict[str, Any] = {
        "startable": None, "measured": False, "connected": False,
        "env_key": key, "env_key_present": key_present,
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    real = binary or detect_one(spec, h, probe_shell=False).binary
    out["binary"] = real
    if not real:
        out["reason"] = ("L-none：這台機器上找不到可執行檔（只有設定目錄）"
                         "⇒ **不量**，不是「起不來」")
        return out
    if not spec.probe_argv:
        out["reason"] = ("沒有已知的一次性非互動叫法 ⇒ **不量**，"
                         "不是「起不來」")
        return out
    mdl = model or os.environ.get("VACANT_AGENT_MODEL", "gemma-4-12b-it-qat")
    lis = _ProbeListener()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacant-startable-"))
    try:
        lis.start()
        fake_home = tmp / "home"
        fake_home.mkdir()
        WIRERS[agent](fake_home, lis.port, tmp / "bk")
        env = dict(os.environ)
        env.pop("VACANT_POSSESS_CFG", None)
        env.pop("VACANT_RUN_PROXY", None)
        if spec.relocate_var:
            env[spec.relocate_var] = str(fake_home / spec.config_dirs[0])
        if agent == "opencode":
            env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        if agent == "claude":
            for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
                      "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_MESSAGING_SOCKET",
                      "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_EXECPATH",
                      "CLAUDE_PID", "AI_AGENT", "CLAUDE_CODE_USE_OPENAI"):
                env.pop(k, None)
            env["DISABLE_TELEMETRY"] = "1"
            env["DISABLE_AUTOUPDATER"] = "1"
        # ⚠ **刻意不補任何金鑰。** 補了就量不到「乾淨環境缺 env_key」那個洞。
        argv = [real] + [a.replace("{model}", mdl) for a in spec.probe_argv]
        out["argv"] = argv
        t0 = time.time()
        rc, so, se = None, "", ""
        # ⚠ **第一條連線一到就收工。** 答案那時候就有了，再等下去只是讓 agent
        #   對著我們的 503 一直重試（2026-09-20 實測 codex 會連 30 次、
        #   把 0.3 秒的答案拖成 24.5 秒）。展場裝機不該為了已知的答案空等。
        try:
            proc = subprocess.Popen(argv, cwd=str(tmp), env=env,
                                    stdin=subprocess.DEVNULL, text=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        except OSError as e:
            out["reason"] = f"叫不起來：{type(e).__name__}: {e}"
            return out
        stopped_early = False
        while True:
            if proc.poll() is not None:
                break
            if lis.connections > 0:
                stopped_early = True
                proc.kill()
                break
            if time.time() - t0 > timeout_s:
                out["timed_out"] = True
                proc.kill()
                break
            time.sleep(0.05)
        try:
            so, se = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:   # pragma: no cover
            proc.kill()
            so, se = proc.communicate()
        rc = proc.returncode if not stopped_early else None
        out["stopped_early"] = stopped_early
        out.update(measured=True, rc=rc,
                   elapsed_s=round(time.time() - t0, 2),
                   # ⚠ `stopped_early` ⇒ `rc` 是 `None`（**我們殺的**，
                   #   不是 agent 自己的退出碼）——不可以讀成 agent 失敗

                   connected=lis.connections > 0,
                   connections=lis.connections,
                   probe_saw=lis.first_line)
        out["startable"] = lis.connections > 0
        head = strip_terminal_noise(
            " ".join((se or so or "").split())[:300])
        out["stderr_head"] = head
        if out["startable"]:
            out["reason"] = (f"起得來：探測 listener 收到 {lis.connections} 條連線"
                             f"（**沒有任何模型呼叫**，另一頭只回 503）")
        else:
            why = ""
            if key and not key_present:
                why = (f"——而且 `{key}` 在現在這個環境裡**沒有值**，"
                       f"那正是 2026-09-20 量到的那個洞")
            out["reason"] = (f"**起不來**：跑完一次都沒有開任何連線{why}。"
                             f"stderr：{head[:180] or '（空）'}")
        return out
    finally:
        lis.close()
        shutil.rmtree(tmp, ignore_errors=True)


# ── 閘門到得了哪些 shell：**當場量，不要猜** ───────────────────────────

_REACH_SENTINEL = ("VACANT_PATH_BEGIN", "VACANT_PATH_END")
_REACH_CMD = ('printf "%s%s%s\\n" "VACANT_PATH_BEGIN" "$PATH" "VACANT_PATH_END"')


def _clean_env(shim_dir: str) -> dict[str, str]:
    """把 shim 目錄從**自己的** `PATH` 裡拿掉，再交給待量的那個 shell。

    ⚠ 不做這一步，量到的就是「子行程繼承了父行程的 PATH」而不是
      「這種 shell 會不會 source 到我們的區塊」——`bash -c` 會假 ✅。
    """
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(
        seg for seg in env.get("PATH", "").split(os.pathsep)
        if seg and seg != shim_dir)
    return env


def _count_on_path(out: str, shim_dir: str) -> tuple[bool, int, str | None]:
    a, b = _REACH_SENTINEL
    clean = strip_terminal_noise(out.replace("\n", ""))
    if a not in clean or b not in clean:
        return False, 0, None
    path = clean.split(a, 1)[1].split(b, 1)[0]
    n = sum(1 for seg in path.split(os.pathsep) if seg == shim_dir)
    return n > 0, n, path


def probe_gate_reach(shim_dir: pathlib.Path, *, timeout_s: float = 30.0
                     ) -> dict:
    """**在這台機器上**逐一量「哪幾種叫起 shell 的方式看得到 shim 目錄」。

    這一支存在的理由是 2026-09-20 的教訓：`install` 說「PATH 寫好了」，
    而 `ssh 主機 '指令'` 與 `bash -c` 底下 shim **根本不在 PATH 上**
    ——**一份說成功的狀態報告，而東西是壞的**。所以不推論，當場量。

    量五種：

    | key | 對應的真實情境 |
    |---|---|
    | `bash -lic` | 人類開終端機 |
    | `bash -lc` | 登入非互動（部分 CI） |
    | `bash -c '. ~/.bashrc'` | **`ssh 主機 '指令'` 的等價路徑**（sshd 起的 bash 會 source `.bashrc`） |
    | `bash -c` | 腳本／cron／`ExecStart=` 直接叫 |
    | `systemd-run --user` | **展場無人值守迴圈那一條** |

    ⚠ **這張表有兩個會讓它變成假綠的陷阱，兩個都是 2026-09-20 當場踩到的。**

      1. **PATH 繼承。** 每一格都先把 shim 目錄從自己的 `PATH` 裡拿掉再量
         （`_clean_env`）。沒做這件事的第一版量出來**五格全 ✅**——因為量的
         那個 python 自己就跑在一個已經 source 過 rc 的 ssh session 裡，
         `bash -c` 只是**繼承**到父行程的 PATH，根本沒讀任何 rc 檔。
      2. **stdin 是不是 socket。** bash 在**非互動**時如果判斷自己是被遠端
         shell daemon 叫起來的（stdin 連著網路連線）就**會**去讀 `~/.bashrc`。
         所以同一行 `bash -c` 在 ssh session 裡（stdin＝socket）是 ✅、
         在 cron／systemd unit 裡（stdin＝`/dev/null`）是 ❌。
         ⇒ 每一格一律 `stdin=DEVNULL`，量的是**腳本／排程那一側**，
         不是「我現在剛好從 ssh 打進來」那一側。

      這兩條合起來的教訓：**這張表不修，它會回報一個比事實樂觀的結果**，
      而那正是本輪在修的那種病。

    ⚠ **量不到什麼，寫在這裡**：
      · `bash -c '. ~/.bashrc'` 是 ssh 那條路的**等價物不是本尊**——真的
        `ssh 主機 '指令'` 還會經過 sshd／pam 的環境，本機量不到那一段。
        真 ssh 的那一格要另外在機器上跑（Linux 那一輪就是這樣量的）。
      · `systemd-run --user` 在沒有 user bus 的 session 裡會直接失敗 ⇒
        那一格回 `available: false`，**那是「沒量到」不是「量到 False」**。
      · 這裡量的是「**shim 在不在 PATH 上**」，不是「**閘門一定會跑**」：
        passthrough 名單與互動 TUI 仍然是刻意的例外（見 `is_passthrough`）。
      · 量到 `on_path: True` 也**不是**「不會被繞過」——打完整路徑照樣跳過。
    """
    sd = str(shim_dir)
    env = _clean_env(sd)
    forms: list[tuple[str, list[str], str]] = [
        ("bash -lic", ["bash", "-lic", _REACH_CMD], "人類開終端機"),
        ("bash -lc", ["bash", "-lc", _REACH_CMD], "登入非互動"),
        ("bash -c '. ~/.bashrc'",
         ["bash", "-c", f". \"$HOME/.bashrc\" >/dev/null 2>&1; {_REACH_CMD}"],
         "ssh 主機 '指令' 的等價路徑（非真 ssh）"),
        ("bash -c", ["bash", "-c", _REACH_CMD], "腳本／cron／ExecStart="),
    ]
    out: dict[str, Any] = {"shim_dir": sd, "forms": {}}
    for key, cmd, why in forms:
        rec: dict[str, Any] = {"why": why, "available": True}
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout_s, env=env,
                               stdin=subprocess.DEVNULL)
            ok, n, _p = _count_on_path(r.stdout or "", sd)
            rec.update(on_path=ok, count=n, rc=r.returncode)
        except (OSError, subprocess.SubprocessError) as e:
            rec.update(available=False, on_path=None,
                       error=f"{type(e).__name__}: {e}",
                       note="⚠ 沒量到，不是量到 False")
        out["forms"][key] = rec
    # systemd --user：展場無人值守那一條
    rec = {"why": "展場無人值守迴圈", "available": False, "on_path": None,
           "note": "⚠ 沒量到，不是量到 False"}
    if shutil.which("systemd-run"):
        unit = f"vacant-gatereach-{int(time.time())}"
        try:
            r = subprocess.run(
                ["systemd-run", "--user", "--quiet", "--wait", "--pipe",
                 "--collect", f"--unit={unit}", "/bin/sh", "-c", _REACH_CMD],
                capture_output=True, text=True, timeout=timeout_s, env=env)
            if r.returncode == 0 or _REACH_SENTINEL[0] in (r.stdout or ""):
                ok, n, _p = _count_on_path(r.stdout or "", sd)
                rec = {"why": "展場無人值守迴圈", "available": True,
                       "on_path": ok, "count": n, "rc": r.returncode}
            else:
                rec["error"] = (r.stderr or "")[:200]
        except (OSError, subprocess.SubprocessError) as e:
            rec["error"] = f"{type(e).__name__}: {e}"
    out["forms"]["systemd-run --user"] = rec
    covered = [k for k, v in out["forms"].items() if v.get("on_path")]
    missed = [k for k, v in out["forms"].items() if v.get("on_path") is False]
    unmeasured = [k for k, v in out["forms"].items() if v.get("on_path") is None]
    dup = {k: v.get("count") for k, v in out["forms"].items()
           if (v.get("count") or 0) > 1}
    out.update(covered=covered, not_covered=missed, unmeasured=unmeasured,
               duplicated=dup)
    interactive_only = bool(covered) and covered == ["bash -lic"]
    out["interactive_only"] = interactive_only
    if interactive_only:
        out["headline"] = ("⚠ **這台機器上閘門只對互動 shell 生效**"
                           "：腳本／排程／systemd unit 叫起來的 agent"
                           "**不會經過閘門**（通道層仍在）。")
    elif missed:
        out["headline"] = ("⚠ **閘門只覆蓋了一部分叫起 agent 的方式**，"
                           f"這幾種收不到：{'、'.join(missed)}。"
                           "（通道層仍在：那幾條路的模型呼叫照樣進 journal。）")
    else:
        out["headline"] = ("量到的這幾種叫法都看得到 shim。"
                           "⚠ 這**不是**「不會被繞過」——打完整路徑照樣跳過。")
    return out


# ── 常駐 proxy 的 OS 監督 ───────────────────────────────────────────────

LAUNCHD_LABEL = "network.vacant.proxyd"
SYSTEMD_UNIT = "vacant-proxyd.service"

LAUNCHD_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>{args}</array>
  <key>EnvironmentVariables</key><dict>
    <key>PYTHONPATH</key><string>{pypath}</string>
    <key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{err}</string>
</dict></plist>
"""

SYSTEMD_SERVICE = """[Unit]
Description=Vacant possess resident proxy (channel layer)
After=network.target

[Service]
Environment=PYTHONPATH={pypath}
ExecStart={cmd}
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
"""


def package_path() -> str:
    """`vacant_network` 這個套件的**父目錄**。

    ⚠ 這一行不是裝飾：常駐 proxy 由 launchd／systemd 起，**cwd 與 sys.path
      都不是開發者的那一套**。原始碼 checkout（沒有 `pip install`）底下
      `import vacant_network` 會直接失敗，而失敗的樣子是「proxy 起不來 ⇒
      preflight 擋下 ⇒ 一個設定檔都沒動」——fail-closed 是對的，但每次都擋
      就沒人裝得起來。所以把套件的父目錄釘進 service 的 `PYTHONPATH`。
      已經 `pip install` 的情況下這一條是多餘但無害的。
    """
    return str(pathlib.Path(__file__).resolve().parents[2])


#: macOS 上 launchd agent **讀不到**的使用者目錄（TCC 隱私保護）。
#: ⚠ 失效的樣子不是「權限錯誤」是**整個 python 直譯器卡在啟動**
#:   （`_PyConfig_InitPathConfig` → `getpath_readlines` → `open()` 不回來），
#:   stdout／stderr 一個字都沒有。2026-09-19 在人類的 Mac 上量到：
#:   `.venv` 在 `~/Documents/GitHub/Vacant` ⇒ launchd job `state = running`、
#:   `pid` 有值、**埠沒有人在聽、log 空的**；同一支 daemon 換成
#:   `/Library/Frameworks/.../python3` ＋ 套件複製到 `/private/tmp` ⇒ 一秒內起來。
#:   ⇒ 這不是「偶爾會失敗」，是**開發者 checkout 底下一定會失敗**。
TCC_PROTECTED = ("Documents", "Desktop", "Downloads",
                 "Library/Mobile Documents")


def tcc_risky(path: str) -> str | None:
    """這個路徑在 macOS 上會不會讓 launchd agent 卡死。回原因或 `None`。"""
    if platform.system() != "Darwin":
        return None
    home = pathlib.Path.home().resolve()
    try:
        rel = pathlib.Path(path).resolve().relative_to(home).as_posix()
    except ValueError:
        return None
    for prot in TCC_PROTECTED:
        if rel == prot or rel.startswith(prot + "/"):
            return f"~/{prot}"
    return None


def _current_user() -> str:
    """現在這個 OS 使用者的名字。

    ⚠ `$USER` 在 systemd unit／cron 底下**可能是空的**，空字串餵給
      `loginctl enable-linger ""` 只會拿到一個看不懂的錯誤。
    """
    for v in ("USER", "LOGNAME"):
        n = os.environ.get(v)
        if n:
            return n
    try:
        import getpass
        return getpass.getuser()
    except Exception:                       # pragma: no cover
        return ""


def read_linger(user: str | None = None) -> str:
    """那個使用者的 `Linger` 現在是什麼：`"yes"` / `"no"` / `"unknown"`。

    ⚠ **`"unknown"` 不是 `"no"`**（鐵律 3：「沒量到」≠「量到 0」）。
      問不出來的時候 `uninstall` 一律不動 linger——寧可留著我們開的，
      也不要關掉別人要的。
    """
    u = user or _current_user()
    if not u or not shutil.which("loginctl"):
        return "unknown"
    try:
        r = subprocess.run(["loginctl", "show-user", u, "--property=Linger"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if r.returncode != 0:
        # 從未登入過的使用者 `show-user` 會失敗，但 linger 檔案還是看得到
        p = pathlib.Path("/var/lib/systemd/linger") / u
        try:
            return "yes" if p.exists() else "unknown"
        except OSError:                     # pragma: no cover
            return "unknown"
    v = (r.stdout or "").strip().split("=", 1)[-1].strip().lower()
    return v if v in ("yes", "no") else "unknown"


def _daemon_argv(python: str, port: int, state: pathlib.Path,
                 upstreams: dict[str, dict]) -> list[str]:
    argv = [python, "-m", "vacant_network.vrun.proxyd",
            "--port", str(port), "--state", str(state)]
    for w, v in upstreams.items():
        argv += ["--upstream", f"{w}={v['url']}"]
    return argv


def install_service(state: pathlib.Path, python: str, port: int,
                    upstreams: dict[str, dict], home: pathlib.Path,
                    backups: pathlib.Path, backend: str | None = None) -> dict:
    """裝一個由 OS 監督、開機就起來的常駐 proxy。

    ⚠ 三種後端，**能力不一樣，`install-status` 會照實講**：
      · `launchd`（macOS）：`RunAtLoad` ＋ `KeepAlive` ⇒ 重開機也會起來。
      · `systemd --user`（Linux）：`Restart=always`；**沒有 linger 的話
        登出就被殺**，所以會試著 `loginctl enable-linger`，失敗就記下來。
      · `bare`（兩者都沒有，例如容器裡）：自己 fork 一個背景行程。
        **重開機不會自己起來**——這一格不准說成「常駐」，`install-status`
        會標 `supervised: no`。
    """
    logs = state / "proxyd"
    logs.mkdir(parents=True, exist_ok=True)
    argv = _daemon_argv(python, port, state, upstreams)
    system = platform.system() if backend in (None, "auto") else {
        "launchd": "Darwin", "systemd": "Linux", "bare": "-"}.get(backend, "-")
    if system == "Darwin" and shutil.which("launchctl"):
        plist = home / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
        body = LAUNCHD_PLIST.format(
            label=LAUNCHD_LABEL,
            args="".join(f"<string>{a}</string>" for a in argv),
            pypath=package_path(),
            log=str(logs / "out.log"), err=str(logs / "err.log"))
        ch = write_tracked(home, plist, body.encode(), backups,
                           note="launchd agent（RunAtLoad+KeepAlive）")
        uid = os.getuid()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LAUNCHD_LABEL}"],
                       capture_output=True)
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            r = subprocess.run(["launchctl", "load", "-w", str(plist)],
                               capture_output=True, text=True)
        return {"backend": "launchd", "label": LAUNCHD_LABEL,
                "unit_file": str(plist), "supervised": True,
                "boot_persistent": True, "rc": r.returncode,
                "stderr": (r.stderr or "")[:400], "changes": [ch.to_json()]}
    if system == "Linux" and shutil.which("systemctl"):
        unit = home / ".config" / "systemd" / "user" / SYSTEMD_UNIT
        cmd = " ".join(_sh_quote(a) for a in argv)
        ch = write_tracked(home, unit,
                           SYSTEMD_SERVICE.format(
                               cmd=cmd, pypath=package_path()).encode(),
                           backups, note="systemd --user unit（Restart=always）")
        subprocess.run(["systemctl", "--user", "daemon-reload"],
                       capture_output=True)
        r = subprocess.run(["systemctl", "--user", "enable", "--now",
                            SYSTEMD_UNIT], capture_output=True, text=True)
        # ⚠ **先問原值再動**：`uninstall` 只能關掉**我們開的**那一次 linger。
        #   原本就是 `yes`（或問不出來）⇒ 一律不動，見 `stop_service`。
        user = _current_user()
        before = read_linger(user)
        linger = subprocess.run(["loginctl", "enable-linger", user],
                                capture_output=True, text=True)
        after = read_linger(user)
        return {"backend": "systemd", "unit": SYSTEMD_UNIT,
                "unit_file": str(unit), "supervised": True,
                "boot_persistent": linger.returncode == 0,
                "linger_rc": linger.returncode, "rc": r.returncode,
                "linger_user": user,
                "linger_before": before, "linger_after": after,
                # **只有這一格是 True 的時候 `uninstall` 才准關 linger**
                "linger_enabled_by_us": (before == "no" and after == "yes"),
                "stderr": (r.stderr or "")[:400], "changes": [ch.to_json()]}
    # 沒有 launchd 也沒有 systemd：自己 fork 一個，**而且說清楚它撐不過重開機**
    out = (logs / "out.log").open("ab")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [package_path()] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    proc = subprocess.Popen(argv, stdout=out, stderr=out, env=env,
                            start_new_session=True)
    return {"backend": "bare", "pid": proc.pid, "supervised": False,
            "boot_persistent": False, "rc": 0, "changes": []}


def stop_service(svc: dict, home: pathlib.Path) -> dict:
    """把常駐 proxy 停掉並取消註冊。**還原不依賴這一步成功。**

    ## `Linger` 的還原規則（2026-09-20 在 vacant-dev 上量到的那個洞）

    `install` 在 Linux 上會 `loginctl enable-linger`。本函式**只在下面兩件事
    同時成立的時候**把它關回去：

      1. `install` 當時量到的 `linger_before == "no"`，**而且**
      2. `install` 之後量到的 `linger_after == "yes"`
         （＝`linger_enabled_by_us` 是 True，那一次真的是我們開的）。

    ⚠ **原本就是 `yes` ⇒ 一律不動。** 那是別人（或使用者自己）要的 linger，
      關掉它會把人家的常駐服務一起弄死。
    ⚠ **`"unknown"` 也一律不動**——鐵律 3：「沒量到」不等於「量到 no」。
    ⚠ 舊版 state（沒有 `linger_before` 這個欄位的那些）⇒ 也不動，並在報告裡
      註明「這一份 state 沒記原值 ⇒ 不敢動」，而不是猜。
    """
    backend = (svc or {}).get("backend")
    res: dict[str, Any] = {"backend": backend}
    if backend == "launchd":
        uid = os.getuid()
        r = subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LAUNCHD_LABEL}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            r = subprocess.run(["launchctl", "unload", "-w",
                                str(svc.get("unit_file", ""))],
                               capture_output=True, text=True)
        res["rc"] = r.returncode
    elif backend == "systemd":
        r = subprocess.run(["systemctl", "--user", "disable", "--now",
                            SYSTEMD_UNIT], capture_output=True, text=True)
        res["rc"] = r.returncode
        res["linger"] = _restore_linger(svc)
    elif backend == "bare":
        pid = svc.get("pid")
        try:
            if pid:
                os.kill(int(pid), 15)
            res["rc"] = 0
        except (OSError, ValueError) as e:
            res["rc"], res["error"] = 1, str(e)
    return res


def _restore_linger(svc: dict) -> dict:
    """照 `stop_service` docstring 那三條規則把 `Linger` 還原。回一份逐項報告。

    ⚠ 報告一定要分得出「**還原了**」「**刻意不動**」「**想動但失敗**」三種。
      全部塞成一個布林會讓「本來就開著所以沒關」長得像「關失敗」。
    """
    user = (svc or {}).get("linger_user") or _current_user()
    before = (svc or {}).get("linger_before")
    by_us = (svc or {}).get("linger_enabled_by_us")
    now = read_linger(user)
    rep: dict[str, Any] = {"user": user, "before": before, "now_before_fix": now}
    if before is None:
        rep.update(action="skipped",
                   reason="這一份 state 沒記 linger 原值（舊版）⇒ 不敢動")
        return rep
    if before != "no":
        rep.update(action="skipped",
                   reason=f"原值是 {before!r}，不是我們開的 ⇒ 不動"
                          "（關掉會弄死別人要的 linger）")
        return rep
    if not by_us:
        rep.update(action="skipped",
                   reason="install 當時沒有真的把它從 no 變成 yes ⇒ 不動")
        return rep
    if now != "yes":
        rep.update(action="skipped", reason=f"現在已經是 {now!r} ⇒ 不用動")
        return rep
    try:
        r = subprocess.run(["loginctl", "disable-linger", user],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        rep.update(action="failed", error=f"{type(e).__name__}: {e}")
        return rep
    after = read_linger(user)
    rep.update(action="restored" if after == "no" else "failed",
               rc=r.returncode, after=after,
               stderr=(r.stderr or "")[:200])
    return rep


def port_is_open(port: int, timeout: float = 0.5) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout):
            return True
    except OSError:
        return False


def pick_port(preferred: int) -> int:
    for p in range(preferred, preferred + 40):
        if not port_is_open(p):
            return p
    raise RuntimeError(f"{preferred}..{preferred + 39} 都被佔用了")


def preflight(port: int, wait_s: float = 25.0) -> dict:
    """**寫任何設定檔之前**先確認那個端點真的在聽，而且真的會轉送。

    這一步是 fail-closed 設計的安全帶：常駐 proxy 起不來的話，五個 agent
    會全部連不上——所以絕不能先改人家的設定檔再來發現 proxy 沒起來。
    """
    import urllib.error
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if port_is_open(port):
            break
        time.sleep(0.3)
    else:
        return {"listening": False, "roundtrip": None,
                "detail": f"{wait_s}s 內 127.0.0.1:{port} 沒有人在聽"}
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/v1/models", timeout=20) as r:
            return {"listening": True, "roundtrip": r.status,
                    "detail": "上游回應了"}
    except urllib.error.HTTPError as e:
        # 502＝上游是 sink（沒人指定）。**那也是「proxy 活著」的證據**，
        # 只是它會拒絕一切——install-status 會把這件事分開講。
        return {"listening": True, "roundtrip": e.code,
                "detail": "proxy 活著；上游回非 2xx（sink ⇒ 502 是預期的）"}
    except Exception as e:                    # pragma: no cover
        return {"listening": True, "roundtrip": None, "detail": str(e)}


# ── install / uninstall / status ───────────────────────────────────────

STATE_VERSION = 1


def install(*, home: pathlib.Path | None = None, port: int = DEFAULT_PORT,
            agents: Iterable[str] | None = None, dry_run: bool = False,
            python: str | None = None, probe_shell: bool = True,
            upstream_overrides: dict[str, str] | None = None,
            skip_path: bool = False, skip_service: bool = False,
            allow_protected_path: bool = False,
            service_backend: str | None = None,
            startable_probe: bool = True,
            gate_reach_probe: bool = True,
            systemd_path_now: bool = False,
            probe_timeout_s: float = 20.0) -> dict:
    h = (home or pathlib.Path.home()).expanduser()
    state = state_home(h)
    py = python or sys.executable
    det = detect(h, probe_shell=probe_shell)
    wanted = list(agents) if agents else [a for a, d in det.items() if d.present]
    missing = [a for a in wanted if not det[a].present]
    ups = discover_install_upstreams(h, upstream_overrides)

    plan = {
        "home": str(h), "state": str(state), "python": py,
        "port_requested": port,
        "detected": {a: d.to_json() for a, d in det.items()},
        "agents": wanted, "not_detected": missing,
        "upstreams": ups,
        "will_write": [str(h / AGENTS[a].config_file) for a in wanted],
        "will_write_shims": [str(state / "bin" / a) for a in wanted],
        "will_touch_rc": [rc for rc in RC_FILES
                          if pathlib.Path(rc.replace("~", str(h))).is_file()],
    }
    if dry_run:
        plan["dry_run"] = True
        return plan
    if not wanted:
        plan["error"] = "一個 agent 都沒偵測到（設定目錄與 PATH 都沒有）"
        return plan

    if (state / "state.json").is_file():
        raise RuntimeError(f"已經裝過了（{state / 'state.json'}）。"
                           f"先 `vacant uninstall`，或用 --force 重裝。")

    # ── 0. macOS TCC 擋門（fail-closed，而且**在動任何東西之前**）────────
    if not skip_service and not allow_protected_path:
        bad = [(w, r) for w, r in
               (("python", tcc_risky(py)), ("套件", tcc_risky(package_path())))
               if r]
        if bad:
            raise RuntimeError(
                "macOS 的 launchd agent 讀不到 "
                + "、".join(f"{w} 在 {r}" for w, r in bad)
                + "（TCC 隱私保護）。**失效的樣子是整個直譯器卡在啟動、log 空的**，"
                  "不是一個看得懂的錯誤，所以這裡先擋下來。三條路："
                  "(1) 把 vacant-network 裝到不受保護的位置（一般 "
                  "`pip install` 進 venv 就不在這幾個目錄裡）；"
                  "(2) `--service bare`（自己 fork，**撐不過重開機**）；"
                  "(3) `--allow-protected-path` 明講要試（preflight 還是會擋）。")

    state.mkdir(parents=True, exist_ok=True)
    backups = state / "backups"
    port = pick_port(port)

    # ── 1. 先把常駐 proxy 起起來並 preflight ──────────────────────────
    svc, pf = {"backend": "skipped", "supervised": False,
               "boot_persistent": False, "changes": []}, {"listening": None}
    if not skip_service:
        svc = install_service(state, py, port, ups, h, backups,
                              backend=service_backend)
        pf = preflight(port)
        if not pf.get("listening"):
            stop_service(svc, h)
            _rollback([FileChange(**c) for c in svc.get("changes", [])])
            raise RuntimeError(
                f"常駐 proxy 起不來（{pf.get('detail')}）⇒ **一個設定檔都沒動**。"
                f"log 在 {state / 'proxyd'}")

    # ── 2. 過了才寫設定檔 ────────────────────────────────────────────
    changes: list[FileChange] = [FileChange(**c) for c in svc.get("changes", [])]
    wired: dict[str, dict] = {}
    # pi 的 extension 要把裝機當下看得到的模型清單烤進去（拿不到＝空，不是錯）
    probed_models: list[str] = []
    if not skip_service and "pi" in wanted:
        from . import piext
        probed_models = piext.probe_models(port)
    for a in wanted:
        try:
            cs = WIRERS[a](h, port, backups, python=py, models=probed_models)
            changes += cs
            wired[a] = {"ok": True, "files": [c.to_json() for c in cs],
                        "measured": CHANNEL_MEASURED.get(a, ""),
                        "verified": bool(CHANNEL_MEASURED.get(a)),
                        # shim 那條路的真模型證據**另一欄**，不餵 `verified`
                        "shim_measured": SHIM_MEASURED.get(a, "")}
        except Exception as e:
            wired[a] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    shim_dir, shims = install_shims(state, wanted, py)
    sysenv: dict[str, Any] = {"file": None, "applied_now": False}
    if not skip_path:
        changes += install_path_block(h, shim_dir, backups)
        # 展場無人值守那一條（`systemd --user` unit）讀不到 shell rc
        sysenv = install_systemd_path_env(h, shim_dir, backups,
                                          apply_now=systemd_path_now)
        changes += [FileChange(**c) for c in sysenv.get("changes", [])]

    # ── 3. 裝完之後**當場量**兩件事，不要留給使用者去猜 ──────────────
    #   (a) 閘門到得了哪幾種 shell（洞 2）；(b) 每個 agent 真的起不起得來（洞 1）。
    reach: dict[str, Any] = {"measured": False,
                             "note": "⚠ 沒量（--no-gate-probe）"}
    if gate_reach_probe and not skip_path:
        reach = probe_gate_reach(shim_dir)
        reach["measured"] = True
    elif skip_path:
        reach = {"measured": False,
                 "note": "--no-path ⇒ 沒動 PATH，閘門要自己接（沒量）"}
    for a in wanted:
        if not wired.get(a, {}).get("ok"):
            continue
        if not startable_probe:
            wired[a]["startable"] = None
            wired[a]["startable_reason"] = "⚠ 沒量（--no-startable-probe）"
            continue
        pr = probe_startable(a, home=h, timeout_s=probe_timeout_s)
        wired[a]["startable"] = pr.get("startable")
        wired[a]["startable_reason"] = pr.get("reason", "")
        wired[a]["startable_detail"] = pr
    # 每個 agent 的沙箱／approval 姿態（讀不出來就 None，不寫空字串）
    posture = {a: read_agent_posture(h, a) for a in wanted}

    st = {
        "version": STATE_VERSION, "installed_at": time.time(),
        "installed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "home": str(h), "python": py, "port": port,
        "upstreams": ups, "agents": wanted, "not_detected": missing,
        "detected": {a: d.to_json() for a, d in det.items()},
        "channel": wired, "shim_dir": str(shim_dir), "shims": shims,
        "service": svc, "preflight": pf, "systemd_path_env": sysenv,
        "gate_reach": reach, "agent_posture": posture,
        "codex_sandbox_requested": codex_sandbox_choice(),
        "warnings": _install_warnings(wired, reach, svc, posture),
        "files": [c.to_json() for c in changes],
    }
    (state / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    return st


def _install_warnings(wired: dict, reach: dict, svc: dict,
                      posture: dict | None = None) -> list[str]:
    """`install` 一裝完就要**大聲講**的事。

    ⚠ 這一支存在的唯一理由：**不准安靜地只覆蓋一半**。裝好之後回一句
      「✓ 已寫入」而 agent 其實起不來（洞 1）、或閘門只對互動 shell 生效
      （洞 2），就是這個專案在抓的那種病——一份說成功的狀態報告，而東西是壞的。
    """
    w: list[str] = []
    bad = [a for a, v in (wired or {}).items() if v.get("startable") is False]
    if bad:
        for a in bad:
            v = wired[a]
            w.append(f"⚠ **{a}：設定寫了，但它在這台機器上起不來** —— "
                     f"{v.get('startable_reason', '')}")
    unk = [a for a, v in (wired or {}).items()
           if v.get("ok") and v.get("startable") is None]
    if unk:
        w.append(f"⚠ 這幾個 agent 的 `startable` **沒量到**（不是起不來）："
                 f"{'、'.join(unk)}")
    if reach and reach.get("measured") and reach.get("headline"):
        if reach.get("not_covered") or reach.get("interactive_only"):
            w.append(reach["headline"])
        if reach.get("duplicated"):
            w.append(f"⚠ shim 目錄在 PATH 上出現超過一次："
                     f"{reach['duplicated']}（區塊有冪等守衛，"
                     f"多半是舊版留下的或別處也加了）")
    want = codex_sandbox_choice()
    if want is None:
        w.append("⚠ `VACANT_POSSESS_CODEX_SANDBOX=keep` ⇒ **codex 的沙箱姿態"
                 "沒有被釘住**（覆寫留痕：這一行就是痕跡）。")
    elif want != CODEX_SANDBOX_DEFAULT:
        w.append(f"⚠ codex 的 `sandbox_mode` 被覆寫成 {want!r}（預設是 "
                 f"{CODEX_SANDBOX_DEFAULT!r}）——**覆寫留痕：這一行就是痕跡**。"
                 f"`danger-full-access` 會讓 agent 的 shell 工具拿到網路，"
                 f"那條路上 wire 是零紀錄而收據照樣 accepted。")
    for a, pv in (posture or {}).items():
        if a == "codex" and pv.get("measured") and \
                pv.get("sandbox_mode") not in (want, None):
            w.append(f"⚠ 寫完之後讀回來的 codex `sandbox_mode` 是 "
                     f"{pv.get('sandbox_mode')!r}，跟要求的 {want!r} 不一樣。")
    if (svc or {}).get("backend") == "bare":
        w.append("⚠ `bare` 後端＝自己 fork，**撐不過重開機**，不准說成「常駐」。")
    if (svc or {}).get("backend") == "systemd" and \
            not (svc or {}).get("boot_persistent"):
        w.append("⚠ `loginctl enable-linger` 沒成功 ⇒ **零 session 之下 proxy "
                 "會被收掉**，展場無人值守不成立。")
    return w


def _rollback(changes: list[FileChange]) -> list[dict]:
    """逐位元還原。**還原之後自己驗一次 sha256**，對不上就記下來。"""
    out = []
    for c in reversed(changes):
        p = pathlib.Path(c.path)
        rec: dict[str, Any] = {"path": c.path, "action": c.action}
        try:
            if c.action == "create":
                if p.is_file():
                    p.unlink()
                rec["result"] = "deleted" if not p.exists() else "still_there"
                rec["ok"] = not p.exists()
            else:
                if not c.backup or not pathlib.Path(c.backup).is_file():
                    rec.update(ok=False, result="備份不見了，沒還原")
                else:
                    shutil.copy2(c.backup, p)
                    now = sha256_file(p)
                    rec.update(ok=(now == c.before_sha256),
                               result="restored", sha256_now=now,
                               sha256_expected=c.before_sha256)
        except OSError as e:
            rec.update(ok=False, result=f"{type(e).__name__}: {e}")
        out.append(rec)
    return out


def uninstall(*, home: pathlib.Path | None = None,
              keep_backups: bool = False) -> dict:
    """逐位元還原，**而且自己驗**。proxy 死著也跑得完（純檔案操作）。"""
    h = (home or pathlib.Path.home()).expanduser()
    state = state_home(h)
    sp = state / "state.json"
    if not sp.is_file():
        return {"ok": False, "error": f"沒有裝過（找不到 {sp}）"}
    st = json.loads(sp.read_text("utf-8"))
    svc_res = stop_service(st.get("service") or {}, h)
    sysenv_res = restore_systemd_path_env(st.get("systemd_path_env") or {})
    # ⚠ `gateshim` 的 per-run 設定目錄**不在 `state["files"]` 裡**（它們是一跑
    #   一個、名字事先不知道），所以 `_rollback` 收不到。收工掃一次，
    #   而且用 `max_age_s=0`：擁有者死了就收，不等 6 小時。
    #   **仍然只收自己建的**（有 owner 標記、pid 已死）。
    try:
        from . import gateshim
        sweep_res = gateshim.sweep_cfg_dirs(max_age_s=0.0)
    except Exception as e:                  # pragma: no cover - 匯入失敗不擋還原
        sweep_res = {"error": f"{type(e).__name__}: {e}"}
    restored = _rollback([FileChange(**c) for c in st.get("files", [])])
    shim_removed = []
    for s in st.get("shims", []):
        p = pathlib.Path(s)
        try:
            if p.is_file():
                p.unlink()
            shim_removed.append({"path": s, "ok": not p.exists()})
        except OSError as e:
            shim_removed.append({"path": s, "ok": False, "error": str(e)})
    shim_dir = pathlib.Path(st.get("shim_dir", ""))
    if shim_dir.is_dir() and not any(shim_dir.iterdir()):
        shim_dir.rmdir()
    all_ok = all(r.get("ok") for r in restored) and \
        all(r.get("ok") for r in shim_removed)
    # ⚠ `bootout`／`disable --now` 回來的時候行程**還沒退完**，馬上量會量到
    #   「埠還開著」而其實它一秒後就關了。等一下再量——**這一格量錯會讓
    #   uninstall 報告說謊**（說沒停掉，其實停了）。
    _port = int(st.get("port") or 0)
    for _ in range(12):
        if not port_is_open(_port):
            break
        time.sleep(0.5)
    report = {"ok": all_ok, "restored": restored, "shims": shim_removed,
              "service": svc_res, "state": str(state),
              "systemd_path_env": sysenv_res,
              "cfg_sweep": sweep_res,
              "port_still_open": port_is_open(_port),
              # ⚠ 誠實邊界：留在機器上的東西（刻意的）
              "kept_on_purpose": [
                  f"{state / 'proxyd'}（常駐 proxy 的 journal）",
                  f"{state / 'uninstall_report.json'}（本份報告）",
              ]}
    (state / "uninstall_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if all_ok:
        sp.unlink()
        if not keep_backups:
            shutil.rmtree(state / "backups", ignore_errors=True)
    return report


def status(*, home: pathlib.Path | None = None, reprobe: bool = False,
           probe_timeout_s: float = 20.0) -> dict:
    """裝了什麼、改了哪些檔、還原會做什麼、現在活著沒有。

    ## 通道層是**三欄**不是一欄（2026-09-20 加的那一欄是 `startable`）

    | 欄 | 問的問題 | 證據 |
    |---|---|---|
    | `wired` | **設定檔寫了嗎** | 檔案 sha256（`files[*]`） |
    | `startable` | **那個 agent 真的起得來嗎** | `probe_startable()` 真跑一次，**不打模型** |
    | `proven` | **通道真的被中介了嗎** | `requests_seen > 0`（唯一算數的那個） |

    ⚠ **三欄不可以互相冒充。** 2026-09-20 量到的病理正是
      `wired = True` 而 agent 完全用不了（codex 缺 `OPENAI_API_KEY`），
      而舊版 `status` 只會印「✓ 已寫入」——**一份說成功的狀態報告，
      而東西是壞的**。
    ⚠ `proven` 的語意**一個字都沒動**：只有 `gateshim` 在一次 run 之後看到
      `requests_seen > 0` 才點得亮（`mark_proven`）。
    ⚠ 三欄都可能是 `None`＝**沒量到**，那不是 `False`（鐵律 3）。

    `reprobe=True` ⇒ 當場重量 `startable` 與 `gate_reach`（會真的把 agent
    跑起來，每個最多 `probe_timeout_s` 秒）；預設讀 `install` 當時量的那一份。
    """
    h = (home or pathlib.Path.home()).expanduser()
    state = state_home(h)
    sp = state / "state.json"
    if not sp.is_file():
        return {"installed": False, "state": str(state)}
    st = json.loads(sp.read_text("utf-8"))
    port = int(st.get("port") or 0)
    hb_path = state / "proxyd" / "heartbeat"
    hb = None
    if hb_path.is_file():
        try:
            hb = json.loads(hb_path.read_text("utf-8"))
        except ValueError:
            hb = None
    files = []
    for c in st.get("files", []):
        p = pathlib.Path(c["path"])
        now = sha256_file(p) if p.is_file() else None
        files.append({
            "path": c["path"], "action": c["action"],
            "before_sha256": c["before_sha256"],
            "after_sha256": c["after_sha256"], "sha256_now": now,
            "changed_since_install": now != c["after_sha256"],
            "backup": c["backup"], "note": c.get("note", ""),
            "uninstall_will": ("刪掉這個檔" if c["action"] == "create"
                               else f"用備份覆寫回 {c['before_sha256'][:12]}…"),
        })
    channel = {}
    for a, v in (st.get("channel") or {}).items():
        startable = v.get("startable")
        s_reason = v.get("startable_reason", "")
        if reprobe and v.get("ok"):
            pr = probe_startable(a, home=h, timeout_s=probe_timeout_s)
            startable, s_reason = pr.get("startable"), pr.get("reason", "")
        spec = AGENTS.get(a)
        channel[a] = {
            "wired": bool(v.get("ok")),
            # ⚠ 三態：True／False／**None＝沒量到**（不是起不來）
            "startable": startable,
            "startable_reason": s_reason,
            "env_key": spec.env_key if spec else None,
            "env_key_present": (bool(os.environ.get(spec.env_key))
                                if spec and spec.env_key else None),
            "proven": bool(v.get("proven")),   # 只有實測過才會是 True
            "measured": v.get("measured", ""),
            "note": ("未實測：寫了設定不等於被中介，"
                     "唯一算數的是 requests_seen"
                     if not v.get("proven") else v.get("proven_note", "")),
            "error": v.get("error"),
        }
    # 常駐 proxy 的 journal 總量。**這是機器層級的證據，不是 per-agent 的**：
    # journal 分不出哪一通是誰打的（沒有 per-agent 標記），所以它只能回答
    # 「通道層活著而且真的有流量」，不能回答「這個 agent 被中介了」。
    # ⚠ 兩件事不可以混講——後者要 `channel[*].proven`。
    jpath = state / "proxyd" / "wire" / "index.jsonl"
    journal: dict[str, Any] = {"exists": jpath.is_file(), "requests_total": 0,
                               "by_path": {}}
    if jpath.is_file():
        import collections
        c: collections.Counter = collections.Counter()
        n = 0
        for line in jpath.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            n += 1
            c[f"{r.get('method')} {r.get('path')} [{r.get('wire')}]"] += 1
        journal["requests_total"] = n
        journal["by_path"] = dict(c)
    reach = st.get("gate_reach") or {"measured": False,
                                     "note": "這一份 state 沒有量過（舊版）"}
    if reprobe and st.get("shim_dir"):
        reach = probe_gate_reach(pathlib.Path(st["shim_dir"]))
        reach["measured"] = True
    return {
        "installed": True, "home": st["home"], "state": str(state),
        "resident_journal": journal,
        "port": port, "endpoint": f"http://127.0.0.1:{port}",
        "proxy_listening": port_is_open(port),
        "proxy_heartbeat": hb,
        "service": {k: st.get("service", {}).get(k)
                    for k in ("backend", "supervised", "boot_persistent",
                              "unit_file", "rc", "linger_before",
                              "linger_enabled_by_us")},
        "linger_now": (read_linger(st.get("service", {}).get("linger_user"))
                       if st.get("service", {}).get("backend") == "systemd"
                       else None),
        "upstreams": st.get("upstreams"),
        "agents": st.get("agents"), "not_detected": st.get("not_detected"),
        "channel": channel,
        "shim_dir": st.get("shim_dir"), "shims": st.get("shims"),
        "systemd_path_env": st.get("systemd_path_env"),
        "gate_reach": reach,
        # ⚠ **當場重讀**而不是回放 install 當時那一份：使用者（或 agent 自己）
        #   裝好之後可能把 sandbox_mode 改掉，而那正是這一欄要抓的事。
        "agent_posture": {a: read_agent_posture(h, a)
                          for a in (st.get("agents") or [])},
        "agent_posture_at_install": st.get("agent_posture"),
        "warnings": st.get("warnings") or [],
        "files": files,
        "gate_bypass": "打完整路徑就跳過 shim ⇒ 閘門不跑（通道仍在）",
    }


def mark_proven(agent: str, requests_seen: int, *,
                home: pathlib.Path | None = None) -> None:
    """把「這個 agent 真的被中介到了」寫進 state。**只有 `requests_seen > 0`
    才算**，由 `gateshim` 在一次 run 結束後呼叫。"""
    h = (home or pathlib.Path.home()).expanduser()
    sp = state_home(h) / "state.json"
    if requests_seen <= 0 or not sp.is_file():
        return
    try:
        st = json.loads(sp.read_text("utf-8"))
        ch = st.setdefault("channel", {}).setdefault(agent, {})
        ch["proven"] = True
        ch["proven_note"] = (f"requests_seen={requests_seen} @ "
                             f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')}")
        sp.write_text(json.dumps(st, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    except (OSError, ValueError):
        pass


# ── CLI ────────────────────────────────────────────────────────────────

def _fmt_status(s: dict) -> str:
    if not s.get("installed"):
        return f"未安裝（state 會在 {s['state']}）"
    L = [f"端點      {s['endpoint']}   在聽：{'是' if s['proxy_listening'] else '**否**'}",
         f"監督      {s['service'].get('backend')}   "
         f"開機自起：{s['service'].get('boot_persistent')}",
         f"上游      " + "  ".join(f"{w}={v['url']}（{v['source']}）"
                                   for w, v in (s.get("upstreams") or {}).items()),
         f"shim 目錄 {s['shim_dir']}",
         "",
         "通道層（三欄：設定寫了／起得來／被中介過。**不可互相冒充**）："]
    for a, v in (s.get("channel") or {}).items():
        flag = "✓ 已寫入" if v["wired"] else f"✗ {v.get('error')}"
        st3 = {True: "✓ 起得來", False: "**✗ 起不來**",
               None: "－ 沒量到"}[v.get("startable")]
        proven = "✓ 已由 requests_seen 證實" if v["proven"] else "**未證實**"
        L.append(f"  {a:<9} 設定 {flag}　啟動 {st3}　中介 {proven}")
        if v.get("startable") is not True and v.get("startable_reason"):
            L.append(f"      {v['startable_reason']}")
        if v.get("env_key") and v.get("env_key_present") is False:
            L.append(f"      ⚠ `{v['env_key']}` 在現在這個環境裡沒有值")
    reach = s.get("gate_reach") or {}
    L += ["", "閘門到得了哪幾種 shell（**這台機器上當場量的**）："]
    if not reach.get("measured"):
        L.append(f"  － 沒量到：{reach.get('note', '')}"
                 "（⚠「沒量到」不是「量到覆蓋」）")
    else:
        for k, v in (reach.get("forms") or {}).items():
            op = v.get("on_path")
            mark = {True: "✅", False: "❌", None: "－ 沒量到"}[op]
            extra = f"（PATH 上 {v.get('count')} 次）" if (v.get("count") or 0) > 1 \
                else ""
            L.append(f"  {k:<26} {mark}{extra}　{v.get('why', '')}")
        L.append(f"  {reach.get('headline', '')}")
    post = s.get("agent_posture") or {}
    if post:
        L += ["", "agent 自己的防護（沙箱／approval，**現在讀到的**）："]
        for a, v in post.items():
            sb = v.get("sandbox_mode")
            ap = v.get("approval_policy")
            f = lambda x: "－ 沒量到" if x is None else repr(x)   # noqa: E731
            L.append(f"  {a:<9} sandbox={f(sb)}　approval={f(ap)}")
            if sb == "danger-full-access":
                L.append("      ⚠ **牆是拆掉的**：agent 的 shell 工具拿得到"
                         "網路 ⇒ 那條路上 wire 零紀錄而收據照樣 accepted")
    if s.get("warnings"):
        L += ["", "⚠ 裝好當時就記下來的警告："]
        L += [f"  {w}" for w in s["warnings"]]
    if s.get("linger_now") is not None:
        svc = s.get("service") or {}
        L += ["", f"Linger    現在 {s['linger_now']}　"
                  f"install 之前 {svc.get('linger_before')}　"
                  f"是我們開的：{svc.get('linger_enabled_by_us')}"
                  f"　（uninstall 只在「是我們開的」時候關回去）"]
    L += ["", "改過的檔（uninstall 會做什麼）："]
    for f in s.get("files", []):
        drift = "  ⚠ 裝好之後又被改過" if f["changed_since_install"] else ""
        L.append(f"  {f['path']}")
        L.append(f"      {f['action']}　{f['note']}")
        L.append(f"      還原：{f['uninstall_will']}{drift}")
        if f["backup"]:
            L.append(f"      備份：{f['backup']}")
    L += ["", f"閘門層：{s['gate_bypass']}"]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="vacant install",
        description="把 Vacant 裝進 agent 自己的常駐設定檔：裝一次就預設在")
    ap.add_argument("action", choices=["install", "uninstall", "status",
                                       "detect"])
    ap.add_argument("--home", default=None, help="目標 HOME（預設 $HOME）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--agent", action="append", default=None,
                    choices=list(AGENTS), help="只裝這幾個（可重複）")
    ap.add_argument("--upstream", action="append", default=[],
                    help="wire=url；沒指定就從使用者現有設定與環境變數推")
    ap.add_argument("--dry-run", action="store_true",
                    help="只印計畫，一個檔都不動")
    ap.add_argument("--no-path", action="store_true",
                    help="不動 shell rc（閘門層要自己把 shim 目錄加進 PATH）")
    ap.add_argument("--no-service", action="store_true",
                    help="不裝常駐 proxy（**通道會連不上**，只給測試用）")
    ap.add_argument("--no-shell-probe", action="store_true",
                    help="偵測時不跑 `bash -lic`（快，但會漏掉不在 PATH 的）")
    ap.add_argument("--python", default=None,
                    help="常駐 proxy 用哪一支 python（預設 sys.executable）")
    ap.add_argument("--service", choices=["auto", "launchd", "systemd", "bare"],
                    default="auto", help="常駐後端；bare＝自己 fork，撐不過重開機")
    ap.add_argument("--allow-protected-path", action="store_true",
                    help="明講要在 macOS 的受保護目錄底下試（會卡死，見 TCC_PROTECTED）")
    ap.add_argument("--no-startable-probe", action="store_true",
                    help="裝完不要真的把 agent 跑起來探測（那一欄會變成「沒量到」）")
    ap.add_argument("--no-gate-probe", action="store_true",
                    help="裝完不要量閘門到得了哪幾種 shell（那一格會變成「沒量到」）")
    ap.add_argument("--systemd-path-now", action="store_true",
                    help="另外對**正在跑的** systemd --user manager 下 "
                         "set-environment PATH（預設只寫 environment.d，"
                         "等 manager 下次啟動才生效）")
    ap.add_argument("--probe-timeout", type=float, default=20.0,
                    help="每個 agent 的 startable 探測上限秒數")
    ap.add_argument("--reprobe", action="store_true",
                    help="status：當場重量 startable 與 gate_reach")
    ap.add_argument("--keep-backups", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    home = pathlib.Path(a.home).expanduser() if a.home else None
    ov = {}
    for it in a.upstream:
        w, _, u = it.partition("=")
        if w and u:
            ov[w] = u
    if a.action == "detect":
        d = {k: v.to_json() for k, v in
             detect(home, probe_shell=not a.no_shell_probe).items()}
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    if a.action == "status":
        s = status(home=home, reprobe=a.reprobe,
                   probe_timeout_s=a.probe_timeout)
        print(json.dumps(s, ensure_ascii=False, indent=2) if a.json
              else _fmt_status(s))
        return 0 if s.get("installed") else 1
    if a.action == "uninstall":
        r = uninstall(home=home, keep_backups=a.keep_backups)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 1
    r = install(home=home, port=a.port, agents=a.agent, dry_run=a.dry_run,
                probe_shell=not a.no_shell_probe, upstream_overrides=ov,
                skip_path=a.no_path, skip_service=a.no_service,
                python=a.python, service_backend=a.service,
                allow_protected_path=a.allow_protected_path,
                startable_probe=not a.no_startable_probe,
                gate_reach_probe=not a.no_gate_probe,
                systemd_path_now=a.systemd_path_now,
                probe_timeout_s=a.probe_timeout)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json
          else _fmt_status(status(home=home)) if not a.dry_run
          else json.dumps(r, ensure_ascii=False, indent=2))
    # ⚠ 裝完的警告要**印在最後**（stderr），不可以被上面那一大坨蓋過去。
    for w in (r.get("warnings") or []):
        print(w, file=sys.stderr)
    return 0 if not r.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
