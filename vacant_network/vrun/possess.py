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
| **通道** | 寫進 agent **自己的常駐設定檔**（`~/.claude/settings.json` 的 `env`、`~/.codex/config.toml`、`~/.config/opencode/opencode.json`、`~/.pi/agent/models.json`、`~/.hermes/config.yaml`） | 關終端機、重開機、開新視窗、**打完整路徑**都照樣指向 proxy。**只有把那幾行刪掉才會失效。** |
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
import time
from typing import Any, Callable, Iterable

from . import envmap

# ── 常數 ────────────────────────────────────────────────────────────────

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
CHANNEL_MEASURED: dict[str, str] = {
    "codex": "",
    "opencode": "",
    "claude": "",
    "pi": "",
    "hermes": "",
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
    ),
    "pi": AgentSpec(
        name="pi",
        config_dirs=(".pi/agent", ".pi"),
        config_file=".pi/agent/models.json",
        binaries=("pi",),
        bin_hints=(".local/bin/pi", ".bun/bin/pi", ".npm-global/bin/pi",
                   "/opt/homebrew/bin/pi", "/usr/local/bin/pi"),
        wire="openai",
        passthrough=frozenset({"--version", "-v", "--help", "-h", "auth",
                               "login", "mcp"}),
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
    doc["provider"] = providers
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    return [write_tracked(home, p, data, backups,
                          note=f"provider.*.options.baseURL ×{len(touched)}"
                               f"（{','.join(touched)}）")]


_TOP_KEY_RE = re.compile(r"^\s*model_provider\s*=")


def wire_codex(home: pathlib.Path, port: int, backups: pathlib.Path,
               **_: Any) -> list[FileChange]:
    """`~/.codex/config.toml`：加一個**新** provider id 並把 `model_provider`
    指過去。

    ⚠ 內建 id `openai` 不准覆寫（codex 會 fail-closed 報錯），所以叫 `vacant`。
    ⚠ `wire_api` 在 0.147.0 上只收 `"responses"`（`envmap.CONFIG_ROUTE["codex"]`）。
    ⚠ **這條路救不了 `codex login`（ChatGPT 帳號）**：那條的模型通道是寫死的
      `wss://chatgpt.com/...`，設定搬不動（`envmap` 誠實邊界 4）。
      也就是說**裝了之後，走 ChatGPT 登入的那條路仍然沒有被中介**。
    """
    p = home / AGENTS["codex"].config_file
    text = p.read_text("utf-8") if p.is_file() else ""
    # 先把上一次留下的區塊整個拿掉（重裝要冪等）
    text = _strip_block(text)
    lines = text.splitlines()
    out, replaced = [], False
    for ln in lines:
        if _TOP_KEY_RE.match(ln) and not replaced:
            out.append(f'model_provider = "{PROVIDER_ID}"   '
                       f'{BEGIN_MARK} 原值：{ln.strip()} {END_MARK}')
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        # 頂層 key 一定要在第一個 table header 之前
        insert_at = next((i for i, ln in enumerate(out)
                          if ln.lstrip().startswith("[")), len(out))
        out.insert(insert_at,
                   f'model_provider = "{PROVIDER_ID}"   {BEGIN_MARK}'
                   f' 原本沒有這個 key {END_MARK}')
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
    return [write_tracked(home, p, data, backups,
                          note=f"model_provider + [model_providers.{PROVIDER_ID}]")]


def wire_pi(home: pathlib.Path, port: int, backups: pathlib.Path,
            **_: Any) -> list[FileChange]:
    """`~/.pi/agent/models.json`。

    ⚠ **這一格沒有在任何機器上被 `requests_seen` 證實過**（`CHANNEL_MEASURED`
      是空字串）。而且 `~/.pi/agent/` 底下同時有 `models-store.json`，
      **哪一份才是 pi 0.85.1 真正讀的那一份，本模組沒有量過**——
      `ops/vacantrun/wrap_agent.sh` 量到的是 `PI_CODING_AGENT_DIR/models.json`，
      那是 relocate 那條路，不保證常駐那條路同名。
      `install-status` 會把這一格標成 `unverified`。
    """
    p = home / AGENTS["pi"].config_file
    doc = json.loads(p.read_text("utf-8")) if p.is_file() else {}
    if not isinstance(doc, dict):
        doc = {}
    model = os.environ.get("VACANT_AGENT_MODEL", "gemma-4-12b-it-qat")
    providers = dict(doc.get("providers") or {})
    for pid, pv in list(providers.items()):
        if isinstance(pv, dict) and "baseUrl" in pv:
            pv = dict(pv)
            pv["baseUrl"] = _base_for("openai", port)
            providers[pid] = pv
    providers[PROVIDER_ID] = {
        "baseUrl": _base_for("openai", port),
        "api": "openai-completions",
        "apiKey": "sk-vacant-possess",
        "compat": {"supportsDeveloperRole": False,
                   "supportsReasoningEffort": False},
        "models": [{"id": model, "name": model,
                    "contextWindow": 262144, "maxTokens": 16384}],
    }
    doc["providers"] = providers
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    return [write_tracked(home, p, data, backups,
                          note=f"providers.*.baseUrl + providers.{PROVIDER_ID}")]


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
            agent=a), encoding="utf-8")
        p.chmod(0o755)
        made.append(str(p))
    return shim_dir, made


def _sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


RC_FILES = ("~/.zshrc", "~/.bashrc", "~/.bash_profile", "~/.profile")


def install_path_block(home: pathlib.Path, shim_dir: pathlib.Path,
                       backups: pathlib.Path) -> list[FileChange]:
    """把 shim 目錄加到 `PATH` 前面，寫進使用者的 shell rc。

    ⚠ 這是本模組唯一會動 shell 設定的地方，而且是一個**有頭有尾的區塊**
      （`>>> vacant possess >>>` … `<<< vacant possess <<<`），`uninstall`
      只拿掉這一段，其餘逐位元不動。
    """
    changes = []
    block = (f"\n{BEGIN_MARK}\n"
             f"export PATH={_sh_quote(str(shim_dir))}:\"$PATH\"\n"
             f"{END_MARK}\n")
    for rc in RC_FILES:
        p = pathlib.Path(rc.replace("~", str(home)))
        if not p.is_file():
            continue
        text = p.read_text("utf-8")
        if BEGIN_MARK in text:
            text = _strip_block(text).rstrip("\n") + "\n"
        changes.append(write_tracked(home, p, (text + block).encode(), backups,
                                     note="PATH 前置 shim 目錄"))
    return changes


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


def _daemon_argv(python: str, port: int, state: pathlib.Path,
                 upstreams: dict[str, dict]) -> list[str]:
    argv = [python, "-m", "vacant_network.vrun.proxyd",
            "--port", str(port), "--state", str(state)]
    for w, v in upstreams.items():
        argv += ["--upstream", f"{w}={v['url']}"]
    return argv


def install_service(state: pathlib.Path, python: str, port: int,
                    upstreams: dict[str, dict], home: pathlib.Path,
                    backups: pathlib.Path) -> dict:
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
    system = platform.system()
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
        linger = subprocess.run(
            ["loginctl", "enable-linger", os.environ.get("USER", "")],
            capture_output=True, text=True)
        return {"backend": "systemd", "unit": SYSTEMD_UNIT,
                "unit_file": str(unit), "supervised": True,
                "boot_persistent": linger.returncode == 0,
                "linger_rc": linger.returncode, "rc": r.returncode,
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
    """把常駐 proxy 停掉並取消註冊。**還原不依賴這一步成功。**"""
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
    elif backend == "bare":
        pid = svc.get("pid")
        try:
            if pid:
                os.kill(int(pid), 15)
            res["rc"] = 0
        except (OSError, ValueError) as e:
            res["rc"], res["error"] = 1, str(e)
    return res


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
            skip_path: bool = False, skip_service: bool = False) -> dict:
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

    state.mkdir(parents=True, exist_ok=True)
    backups = state / "backups"
    port = pick_port(port)

    # ── 1. 先把常駐 proxy 起起來並 preflight ──────────────────────────
    svc, pf = {"backend": "skipped", "supervised": False,
               "boot_persistent": False, "changes": []}, {"listening": None}
    if not skip_service:
        svc = install_service(state, py, port, ups, h, backups)
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
    for a in wanted:
        try:
            cs = WIRERS[a](h, port, backups)
            changes += cs
            wired[a] = {"ok": True, "files": [c.to_json() for c in cs],
                        "measured": CHANNEL_MEASURED.get(a, ""),
                        "verified": bool(CHANNEL_MEASURED.get(a))}
        except Exception as e:
            wired[a] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    shim_dir, shims = install_shims(state, wanted, py)
    if not skip_path:
        changes += install_path_block(h, shim_dir, backups)

    st = {
        "version": STATE_VERSION, "installed_at": time.time(),
        "installed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "home": str(h), "python": py, "port": port,
        "upstreams": ups, "agents": wanted, "not_detected": missing,
        "detected": {a: d.to_json() for a, d in det.items()},
        "channel": wired, "shim_dir": str(shim_dir), "shims": shims,
        "service": svc, "preflight": pf,
        "files": [c.to_json() for c in changes],
    }
    (state / "state.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    return st


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
    report = {"ok": all_ok, "restored": restored, "shims": shim_removed,
              "service": svc_res, "state": str(state),
              "port_still_open": port_is_open(int(st.get("port") or 0))}
    (state / "uninstall_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if all_ok:
        sp.unlink()
        if not keep_backups:
            shutil.rmtree(state / "backups", ignore_errors=True)
    return report


def status(*, home: pathlib.Path | None = None) -> dict:
    """裝了什麼、改了哪些檔、還原會做什麼、現在活著沒有。

    ⚠ **`wired` 與 `proven` 是兩欄**：前者＝設定檔寫了；後者＝真的看過
      `requests_seen > 0`。**永遠不把前者說成後者**（`envmap` 誠實邊界 1）。
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
        channel[a] = {
            "wired": bool(v.get("ok")),
            "proven": bool(v.get("proven")),   # 只有實測過才會是 True
            "measured": v.get("measured", ""),
            "note": ("未實測：寫了設定不等於被中介，"
                     "唯一算數的是 requests_seen"
                     if not v.get("proven") else v.get("proven_note", "")),
            "error": v.get("error"),
        }
    return {
        "installed": True, "home": st["home"], "state": str(state),
        "port": port, "endpoint": f"http://127.0.0.1:{port}",
        "proxy_listening": port_is_open(port),
        "proxy_heartbeat": hb,
        "service": {k: st.get("service", {}).get(k)
                    for k in ("backend", "supervised", "boot_persistent",
                              "unit_file", "rc")},
        "upstreams": st.get("upstreams"),
        "agents": st.get("agents"), "not_detected": st.get("not_detected"),
        "channel": channel,
        "shim_dir": st.get("shim_dir"), "shims": st.get("shims"),
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
         "通道層（寫進 agent 自己的常駐設定檔）："]
    for a, v in (s.get("channel") or {}).items():
        flag = "✓ 已寫入" if v["wired"] else f"✗ {v.get('error')}"
        proven = "已由 requests_seen 證實" if v["proven"] else "**未證實**"
        L.append(f"  {a:<9} {flag}　中介{proven}")
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
        s = status(home=home)
        print(json.dumps(s, ensure_ascii=False, indent=2) if a.json
              else _fmt_status(s))
        return 0 if s.get("installed") else 1
    if a.action == "uninstall":
        r = uninstall(home=home, keep_backups=a.keep_backups)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 1
    r = install(home=home, port=a.port, agents=a.agent, dry_run=a.dry_run,
                probe_shell=not a.no_shell_probe, upstream_overrides=ov,
                skip_path=a.no_path, skip_service=a.no_service)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json
          else _fmt_status(status(home=home)) if not a.dry_run
          else json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if not r.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
