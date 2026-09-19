"""這支在架構裡承重什麼：**閘門層那一層「行程結束時接手」的東西**。

`vacant install` 在 `~/.vacant/possess/bin/` 放五支同名的小 shell 腳本，並且
把那個目錄加到 `PATH` 前面。使用者打 `pi -p "做這件事"` 時先打到 shim，
shim `exec` 進本模組，本模組才去找真正的 `pi` 並且把它包進 `launcher.run()`。

⚠ **打完整路徑（`/usr/local/bin/pi`）就跳過這一層。** 通道層仍然成立
（那是寫在 agent 自己的設定檔裡的），但**閘門不會跑、不會有裁決收據**。
本檔任何一處都不准把這一層寫成「不會被繞過」。

## 本模組的兩個階段（同一支檔，靠 `--exec` 分）

  · **外層**（shim 呼叫）：找真 binary → 決定要不要 gate → 找驗收套件 →
    `launcher.run()` → **把退出碼映射成裁決** → 落一份 `possess.json`。
  · **內層**（`--exec`，被 `launcher` 當成 agent 命令 spawn）：這時候
    `$VACANT_RUN_PROXY` 已經有值了，所以在這裡才寫得出 per-run 的
    relocate 設定（`CODEX_HOME`／`PI_CODING_AGENT_DIR`／`HERMES_HOME`／
    `OPENCODE_CONFIG_CONTENT`／`CLAUDE_CONFIG_DIR`），然後 `exec` 真 binary，
    **argv 逐位元照抄使用者打的那一串**。

  內層用 relocate 而不是靠使用者那份常駐設定，有一個**設計上的理由**：
  經過閘門的那一跑要指向**這一跑自己的 ephemeral proxy**（收據的 wire log
  才對得起來），不是常駐的那個共用端點。兩者的優先順序由 relocate 變數
  決定——relocate 把整份設定搬走，常駐那一份在那一跑裡根本不會被讀到。

## 退出碼（⚠ 這是本模組最重要的規格）

| 碼 | 意思 |
|---|---|
| `0` | **驗收真的跑了而且過了** |
| `20` | 驗收跑了沒過 ⇒ 拒交（`launcher.EXIT_REFUSED`） |
| `21` | **沒有驗收可跑**：只中介、沒閘門（`stop_reason="ungated"`） |
| `22` | `infra_void`（`launcher.EXIT_VOID`） |
| `23` | **`requests_seen == 0`**：這一跑沒有任何模型呼叫經過 proxy |
| `24` | **B 級**：圍牆成立、工具層未閘門（`attest.TIER_B`） |
| `25` | **B′ 級**：工具層有紀錄、模型通道沒（完整）被看到（`attest.TIER_B_PRIME`） |
| `26` | **C 級**：未受控 ⇒ **拒發收據**（`attest.TIER_C`） |
| 其他 | passthrough 模式：原樣透傳真 binary 的退出碼 |

`24`／`25`／`26` 是 2026-09-20 加的（`DECISION_20260920_COMPLETE_MEDIATION.md`
§三）。**`0`／`20`／`21`／`22`／`23` 的語意一個字都沒動**——那五個碼回答的是
「這一跑的**裁決**是什麼」，新的三個回答的是「這一跑的**紀錄能不能拿來
究責**」，兩個維度正交。新碼只有在 `VACANT_ATTEST=fail` 之下才會蓋過去。

## 認證模式 `VACANT_ATTEST`（⚠ 預設 `warn`，而那是一個**明講的偏離**）

| 值 | 收據 | 退出碼 |
|---|---|---|
| `off` | 有 `attestation` 但 `tier=null`＝**沒量到** | 完全不受影響 |
| `warn`（預設） | 有 `attestation` ＋ `attested: false`＝**未認證** | **不受影響**（印警告） |
| `fail` | C 級**拒發收據**（改落一份 `NOT_CERTIFIED.json`） | B→24、B′→25、C→26 |

裁決 §二 P0 的原文是「任一不成立 ⇒ 收據寫『未認證』、**退出碼不是 0**」，
也就是預設應該是 `fail`。這裡預設 `warn`，理由要寫清楚、不要假裝沒有：

  · 沒有 root 的 macOS **永遠**到不了 A 級（沒有 bwrap ⇒ 沒有圍牆），
    預設 `fail` 等於今天起 macOS 上每一跑都拒發收據——那是產品層級的停擺，
    而裁決講的是展場那條線（§三-3「展場只允許 A 級」）。
  · 而且它會動到既有退出碼的實際行為，那是本輪驗收第 6 項明文禁止的。

⇒ **「未認證」那一半照做**（`warn` 之下收據照樣帶 `attested: false` ＋ `tier`
  ＋ 那一級**能說的那句話**，沒有人讀得成「這張是認證過的」）；
  **「退出碼不是 0」那一半要明講才打開**。
  **展場的 profile 必須設 `VACANT_ATTEST=fail`。**

`21` 是 2026-09-19 人類點名要的那一格：**「只中介不跑閘門」不可以長得像
「跑了驗收而且過了」**。`launcher.exit_code()` 現在把 `ungated` 判成 0
（因為 `refused` 是 False），本模組**不改 launcher**（那會動到已歸檔資料的
可比性），而是在 shim 這一層把它分出來。

`23` 是同一條紀律的另一面。2026-09-19 的負控制量到：
`rs=0`／`wire={}`／`agent_rc=0`／`stop_reason=visible_fail`／exit 20／
`chain_ok=true` —— **除了 `requests_seen`，每個欄位都跟一個合法的拒交格
一模一樣**。所以「沒量到中介」必須有自己的碼，不可以混進 20。

⚠ `23` 蓋過 `0`／`20`／`21`（`22` 除外）。理由：沒有中介的證據時，
那一格的裁決**不可歸因**——不是「拒交」也不是「通過」。
`VACANT_POSSESS_RS0=warn` 可以降級成只印警告（預設是 `fail`）。

## per-run 設定目錄的收尾契約（**誰刪、什麼時候刪、刪不掉怎麼辦**）

背景是量出來的，不是推論：codex 會把它的 plugins git repo **整個 clone 進**
per-run 的 `CODEX_HOME` ⇒ **每跑一格約 100 MB**。2026-09-20 在 vacant-dev 上
5 格留下 **400 MB**（那台 2.5 G 餘裕的 16%），而 `uninstall` 不碰它。
**無人值守迴圈照這樣跑會把磁碟吃光，而那正是展場的形狀。**

收尾分三層，**一層比一層弱，但沒有一層假裝自己是最後一道**：

| 層 | 誰刪 | 什麼時候 | 撐得過什麼 |
|---|---|---|---|
| 1 | 外層 `run_gate` 的 `finally` | `launcher.run()` 回來之後（正常結束、agent 崩掉、Python 例外都算） | 一般失敗 |
| 2 | `run_gate` 裝的 `SIGTERM`／`SIGHUP` handler ⇒ `SystemExit` ⇒ 仍然走 `finally` | 被 systemd `stop`／被人 `kill` | 溫和的終止 |
| 3 | **下一跑開場的掃地機** `sweep_cfg_dirs()` | 每次 `run_gate` 一開始 | **`SIGKILL`／斷電／`kill -9`** |

⚠ **第 3 層是唯一撐得過 `SIGKILL` 的**，而它的誠實說法是
**「不累積」不是「當下不留」**：被 `kill -9` 的那一格**會**留下一份，
直到**下一次有人經過閘門**（或有人手動 `--sweep`）才被收掉。
所以穩態用量是 **O(1) 而不是 O(N)**，峰值是「1 份在跑的 ＋ 至多 1 份上一次被
殺掉的」。**如果迴圈從此再也不跑，那一份就會一直在**——那種情況下迴圈本來
就停了，但這句話要說出來，不可以讓人讀成「保證零殘留」。

⚠ **掃地機只收得到自己建的東西**，這是刻意的：
  · 只掃**專屬父目錄** `$TMPDIR/vacant-possess/`，不掃 `$TMPDIR` 本身。
  · 只刪**裡面有 `.vacant-possess-owner.json` 標記**的子目錄。
    沒有標記 ⇒ 記成 `skipped_not_ours`，**一個 byte 都不碰**。
  · 擁有者三態（`_owner_state`）：`alive`（pid 在、**而且行程啟動時刻
    對得上**）不刪；`dead`（pid 不見了，或 pid 在但啟動時刻對不上＝被重用）
    當場收；`unknown`（**問不出來**）退回歲數門檻（`SWEEP_MAX_AGE_S`，
    預設 6 小時，`VACANT_POSSESS_SWEEP_AGE_S` 可調）。
    ⚠ `unknown` **不等於** `dead`——猜錯的代價是刪掉別人正在用的設定。
  · 「行程啟動時刻」那一格是 `kill -9` 的垃圾能在**下一跑**就被收掉的原因；
    沒有它就只剩歲數門檻，那表示垃圾要躺 6 小時，而無人值守的迴圈在那之前
    照樣是線性成長。
  · `VACANT_POSSESS_CFG` 是呼叫端自己指定的位置 ⇒ **本模組不建也不刪**，
    誰指定誰負責。

⚠ **刪不掉的時候**（權限、NFS busy、檔案被佔住）：不 raise、不靜默。
  (i) 把失敗逐筆記進 `<run_dir>/possess.json` 的 `cleanup` 欄並印到 stderr；
  (ii) 把 owner 標記改寫成 `pid: 0`，**讓下一次掃地機收得到**
       （`rmtree` 有可能先把標記刪掉，所以是「改寫」不是「保留」）；
  (iii) 退出碼**不變**——磁碟沒清乾淨不是裁決，不可以污染 0／20／21／23。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import uuid

from . import attest, hookcli, launcher, possess

EXIT_UNGATED = 21
EXIT_NO_MEDIATION = 23

#: 分級的三個新碼（裁決 §三）。**不可以重用 0／20／21／22／23**——那五個是
#: 「裁決是什麼」，這三個是「紀錄能不能拿來究責」，混在一起就分不出來了。
EXIT_TIER_B = 24
EXIT_TIER_B_PRIME = 25
EXIT_TIER_C = 26

#: 認證模式。**預設 `warn`**，理由與偏離寫在本模組 docstring。
ATTEST_MODES = ("off", "warn", "fail")


def attest_mode() -> str:
    m = (os.environ.get("VACANT_ATTEST") or "warn").strip().lower()
    return m if m in ATTEST_MODES else "warn"


def apply_tier_exit(verdict: int, tier: str | None, mode: str) -> int:
    """級別要不要蓋掉裁決的退出碼。**純函式，因為這一條規則要被逐格驗。**

    三條規則，每一條都有理由：

      1. 只有 `mode == "fail"` 才蓋。`warn`／`off` 之下退出碼一個字不動
         （本模組 docstring 的「明講的偏離」）。
      2. **A 級不蓋**（`attest.TIER_EXIT[A] is None`）：受控的那一跑，
         退出碼就是它的裁決。
      3. **`22`（`infra_void`）不蓋。** 那一格什麼都沒量到，在它上面再貼一個
         級別等於用一個沒發生的跑去講受不受控。紀律逐字沿用 `23`
         （`23` 蓋 `0`／`20`／`21`，唯獨不蓋 `22`）。
    """
    if tier is None or mode != "fail" or verdict == launcher.EXIT_VOID:
        return verdict          # 沒量到級別 ⇒ 不蓋（鐵律 3）
    return attest.TIER_EXIT.get(tier) or verdict

#: per-run 設定目錄的**專屬父目錄**（在 `$TMPDIR` 底下）。
#: ⚠ 掃地機只掃這底下——**不掃 `$TMPDIR` 本身**，免得刪到不是自己建的東西。
CFG_PARENT_NAME = "vacant-possess"

#: 每個 per-run 目錄裡的擁有者標記。**沒有這個檔的目錄，掃地機一律不碰。**
OWNER_MARK = ".vacant-possess-owner.json"

#: 擁有者 pid 死了**而且**超過這個歲數才收。
#: 兩個條件都要的理由：pid 會被重用，只看 pid 會刪到別人正在用的目錄。
SWEEP_MAX_AGE_S = 6 * 3600

#: 自動找驗收套件的規則，**由近而遠，第一個命中就停**。
#: 每一條都要能在收據上被指名（`suite_source`）。
SUITE_DIRNAMES = (".vacant/suite", "tests_visible")
SUITE_TOML = (".vacant.toml",)


def resolve_suite(cwd: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """回 `(套件目錄, 是哪一條規則命中的)`。找不到回 `(None, "none")`。

    ⚠ **回 `None` 不是錯誤**，是「這一跑沒有閘門」——呼叫端要把它落成
      `ungated`／exit 21，**不准讓它長得像通過**。
    """
    env = os.environ.get("VACANT_SUITE")
    if env:
        p = pathlib.Path(env).expanduser()
        if p.is_dir():
            return p, "env:VACANT_SUITE"
    here = cwd.resolve()
    for d in [here, *here.parents]:
        for name in SUITE_DIRNAMES:
            cand = d / name
            if cand.is_dir() and any(cand.glob("test_*.py")):
                return cand, f"dir:{name}"
        for tname in SUITE_TOML:
            t = d / tname
            if t.is_file():
                try:
                    import tomllib
                    doc = tomllib.loads(t.read_text("utf-8"))
                except Exception:
                    continue
                s = (doc.get("suite")
                     or (doc.get("tool") or {}).get("vacant", {}).get("suite"))
                if s:
                    cand = (d / str(s)).resolve()
                    if cand.is_dir():
                        return cand, f"toml:{tname}"
        if (d / ".git").exists():
            break                       # 走到專案根就停，不要爬到 $HOME
    return None, "none"


def _inject_upstreams_from_state() -> dict[str, str]:
    """把 `vacant install` 當時記下來的上游補進環境變數，給 `launcher` 用。

    **只在那個變數還沒有值的時候補**——使用者明講的永遠優先。
    """
    out: dict[str, str] = {}
    sp = possess.state_home() / "state.json"
    if not sp.is_file():
        return out
    try:
        st = json.loads(sp.read_text("utf-8"))
    except (OSError, ValueError):
        return out
    for wire, var in (("openai", "VACANT_RUN_UPSTREAM_OPENAI"),
                      ("anthropic", "VACANT_RUN_UPSTREAM_ANTHROPIC")):
        url = ((st.get("upstreams") or {}).get(wire) or {}).get("url")
        if url and not os.environ.get(var):
            os.environ[var] = url
            out[wire] = url
    return out


def real_binary(agent: str, shim_dir: str | None) -> str | None:
    """找真正的可執行檔——**把 shim 目錄從 PATH 拿掉再找**，否則自己找到自己。

    `VACANT_POSSESS_REAL_BIN` 明講的優先（agent 不在 PATH 上時用得到，
    也是負控制把 `/bin/true` 放進 agent 位置的那個鉤子）。
    """
    explicit = os.environ.get("VACANT_POSSESS_REAL_BIN")
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep)
             if p and (not shim_dir or os.path.abspath(p) !=
                       os.path.abspath(shim_dir))]
    found = shutil.which(agent, path=os.pathsep.join(parts))
    if found:
        return found
    spec = possess.AGENTS.get(agent)
    if spec:
        home = pathlib.Path.home()
        for hint in spec.bin_hints:
            p = pathlib.Path(hint) if hint.startswith("/") else home / hint
            if p.is_file() and os.access(p, os.X_OK):
                return str(p)
    return None


def is_passthrough(agent: str, argv: list[str]) -> bool:
    """這一次呼叫該不該被閘門包起來。

    `codex --version`／`claude mcp list`／`opencode auth` 這種**不是在交付工作**
    的呼叫要原樣放過去——包起來只會壞掉使用者的日常操作，然後 Vacant 被解除
    安裝。**這是一條已知的繞過路**（打 `--help` 當然不會被 gate），
    寫在這裡是為了它是明示的、數得出來的，而不是一個意外。
    """
    spec = possess.AGENTS.get(agent)
    if spec is None:
        return True
    if not argv:
        return True                     # 沒參數＝多半是互動 TUI，見下
    for a in argv:
        if a in spec.passthrough:
            return True
    if argv and not argv[0].startswith("-") and argv[0] in spec.passthrough:
        return True
    # 互動 TUI（stdin 是終端機）預設不 gate：把一個互動 session 凍結起來跑
    # 驗收會毀掉使用者的工作流。`VACANT_POSSESS_GATE_TTY=1` 可以打開。
    if sys.stdin.isatty() and os.environ.get(
            "VACANT_POSSESS_GATE_TTY", "") not in ("1", "true", "yes"):
        return True
    return False


# ── per-run 設定目錄：建立／釋放／掃地 ─────────────────────────────────
#    契約寫在本模組 docstring 的「per-run 設定目錄的收尾契約」那一節。

def cfg_parent() -> pathlib.Path:
    """per-run 設定目錄的專屬父目錄。`VACANT_POSSESS_TMPROOT` 可以搬走（測試用）。"""
    root = (os.environ.get("VACANT_POSSESS_TMPROOT")
            or os.environ.get("TMPDIR") or "/tmp")
    return pathlib.Path(root) / CFG_PARENT_NAME


def new_cfg_dir(tag: str) -> pathlib.Path:
    """建一個帶擁有者標記的 per-run 目錄。**標記是掃地機認得出自己人的唯一依據。**"""
    d = cfg_parent() / f"{tag}-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    _write_owner(d, os.getpid(), time.time())
    return d


def _proc_start_key(pid: int) -> str | None:
    """這個 pid 的**行程啟動時刻**，用來分辨「同一個行程」與「pid 被重用」。

    有這一格，掃地機才敢在**下一跑就**收掉被 `kill -9` 的那一份，而不必等
    歲數門檻——不然 `SIGKILL` 的垃圾會躺到 6 小時後才被收，無人值守的迴圈
    在那之前照樣是線性成長。

    回 `None` ＝ **這台機器上問不出來**（不是「沒有」）⇒ 掃地機退回保守的
    歲數門檻。鐵律 3。
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    stat = pathlib.Path(f"/proc/{pid}/stat")
    if stat.is_file():                      # Linux
        try:
            raw = stat.read_text("utf-8")
            # comm 欄位可能含空白與 `)`，所以從最後一個 `)` 之後開始切
            fields = raw[raw.rfind(")") + 1:].split()
            return fields[19] if len(fields) > 19 else None   # starttime
        except (OSError, IndexError, ValueError):
            return None
    try:                                    # macOS／BSD
        r = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    out = (r.stdout or "").strip()
    return out or None


def _write_owner(d: pathlib.Path, pid: int, created: float,
                 note: str = "", start_key: str | None = "") -> None:
    key = _proc_start_key(pid) if start_key == "" else start_key
    try:
        (d / OWNER_MARK).write_text(json.dumps(
            {"pid": pid, "created": created, "note": note,
             "start_key": key,
             "created_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z",
                                          time.localtime(created))},
            ensure_ascii=False), encoding="utf-8")
    except OSError:                         # pragma: no cover - 磁碟滿了之類
        pass


def _owner_state(pid, start_key) -> str:
    """擁有者現在是什麼狀態：`"alive"` / `"dead"` / `"unknown"`。

    ⚠ 三態不是兩態。`"unknown"`（問不出來）**不等於** `"dead"`——鐵律 3，
      而且在這裡猜錯的代價是刪掉別人正在用的設定目錄。
    """
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return "dead"                       # pid 根本不在 ⇒ 確定死了
    except PermissionError:
        pass                                # 存在，只是不是我的
    except (OSError, ValueError, TypeError):
        return "unknown"
    now_key = _proc_start_key(pid)
    if start_key and now_key and now_key != start_key:
        return "dead"                       # pid 被重用了 ⇒ 原本那個死了
    if start_key and now_key and now_key == start_key:
        return "alive"
    return "unknown" if not start_key else "alive"


def sweep_cfg_dirs(*, keep: pathlib.Path | None = None,
                   max_age_s: float | None = None,
                   parent: pathlib.Path | None = None,
                   now: float | None = None) -> dict:
    """收掉**自己建的**、擁有者已經死掉而且夠老的 per-run 目錄。

    這是收尾契約的第 3 層，也是**唯一撐得過 `SIGKILL`／斷電**的一層：
    被 `kill -9` 的那一格會留到**下一次有人經過閘門**才被收掉。
    所以它保證的是「**不隨格數累積**」，**不是**「當下不留」。

    ⚠ **四道不刪的門，每一道都是刻意的**：
      1. 只看專屬父目錄底下的**直屬**子目錄（不遞迴、不掃 `$TMPDIR` 本身）；
      2. 沒有 `OWNER_MARK` 的 ⇒ `skipped_not_ours`，**不碰**；
      3. 擁有者 `alive`（pid 在、而且行程啟動時刻對得上）⇒ `kept_alive`，**不碰**；
      4. 擁有者 `unknown`（**問不出來**，不是「死了」）⇒ 退回歲數門檻：
         年紀 < `max_age_s` ⇒ `kept_young`，**不碰**。

    擁有者 `dead`（pid 不見了，或 pid 還在但**啟動時刻對不上**＝被重用）
    ⇒ **不等歲數門檻，當場收**。這一條就是「`kill -9` 的那一份在**下一跑**
    就被收掉」的來源；沒有它，`SIGKILL` 的垃圾要躺到 6 小時後。

    回一份逐筆報告；刪失敗的落在 `failed`，**不 raise**——磁碟沒清乾淨
    不是裁決，不可以污染退出碼。
    """
    par = parent or cfg_parent()
    age = (max_age_s if max_age_s is not None else
           float(os.environ.get("VACANT_POSSESS_SWEEP_AGE_S", SWEEP_MAX_AGE_S)))
    t = now if now is not None else time.time()
    rep: dict = {"parent": str(par), "max_age_s": age, "removed": [],
                 "kept_alive": [], "kept_young": [], "skipped_not_ours": [],
                 "failed": [], "bytes_removed": None}
    if not par.is_dir():
        return rep
    keep_r = str(keep.resolve()) if keep else None
    try:
        children = sorted(par.iterdir())
    except OSError as e:                    # pragma: no cover
        rep["failed"].append({"path": str(par), "error": str(e)})
        return rep
    for d in children:
        if not d.is_dir() or (keep_r and str(d.resolve()) == keep_r):
            continue
        mark = d / OWNER_MARK
        if not mark.is_file():
            # ⚠ 不是我們建的（或標記被刪了）⇒ **不要順手刪別人的東西**
            rep["skipped_not_ours"].append(str(d))
            continue
        try:
            info = json.loads(mark.read_text("utf-8"))
        except (OSError, ValueError):
            rep["skipped_not_ours"].append(str(d))
            continue
        pid = info.get("pid")
        created = float(info.get("created") or 0.0)
        who = _owner_state(pid, info.get("start_key")) if pid else "dead"
        if who == "alive":
            rep["kept_alive"].append({"path": str(d), "pid": pid})
            continue
        if who == "unknown" and (t - created) < age:
            # ⚠ 問不出來 ⇒ 退回歲數門檻，**寧可晚一點收也不要刪錯**
            rep["kept_young"].append({"path": str(d), "owner": "unknown",
                                      "age_s": round(t - created, 1)})
            continue
        r = _rmtree_reporting(d)
        (rep["removed"] if r.get("ok") else rep["failed"]).append(r)
    return rep


def _dir_bytes(d: pathlib.Path) -> int | None:
    total = 0
    try:
        for root, _dirs, files in os.walk(d):
            for f in files:
                try:
                    total += os.lstat(os.path.join(root, f)).st_size
                except OSError:
                    pass
    except OSError:                         # pragma: no cover
        return None
    return total


def _rmtree_reporting(d: pathlib.Path) -> dict:
    """刪一個目錄，**刪不掉就把 owner 標記改寫成死的**，讓下一次掃地機收得到。

    ⚠ `shutil.rmtree` 有可能**先把標記刪掉才失敗**，所以這裡是「改寫」不是
      「保留」——不改寫的話那個目錄會變成 `skipped_not_ours`，從此沒人收。
    """
    size = _dir_bytes(d)
    rec: dict = {"path": str(d), "bytes": size}
    try:
        shutil.rmtree(d)
    except OSError as e:
        rec.update(ok=False, error=f"{type(e).__name__}: {e}")
    if d.exists():
        rec.setdefault("ok", False)
        rec.setdefault("error", "rmtree 回來了但目錄還在")
        _write_owner(d, 0, 0.0, note="release/sweep 失敗，交給下一次掃地機")
    else:
        rec["ok"] = True
    return rec


def release_cfg_dir(cfg: pathlib.Path | None) -> dict:
    """收尾契約的第 1／2 層：**這一跑自己建的目錄，這一跑自己刪**。

    `cfg is None` ＝ 這一跑用的是呼叫端給的 `VACANT_POSSESS_CFG`，
    **誰指定誰負責，本函式不刪**。
    """
    if cfg is None:
        return {"owned": False,
                "note": "VACANT_POSSESS_CFG 由呼叫端指定 ⇒ 本模組不建也不刪"}
    if not cfg.exists():
        return {"owned": True, "path": str(cfg), "ok": True,
                "note": "已經不在了"}
    r = _rmtree_reporting(cfg)
    r["owned"] = True
    return r


# ── 內層：被 launcher spawn 的那一段 ───────────────────────────────────

def exec_inner(agent: str, argv: list[str]) -> int:
    """`$VACANT_RUN_PROXY` 已經有值了 ⇒ 現寫一份 per-run 設定，然後 exec 真 binary。

    ⚠ 這裡是 `ops/vacantrun/wrap_agent.sh` 那五段接線的 Python 版，**判準一樣**
      （`envmap.CONFIG_ROUTE`）。差別只有一個：wrap_agent.sh 自己組 argv，
      本函式**照抄使用者打的那一串**——「裝一次就在」的前提是使用者的命令
      一個字都不用改。
    """
    base = (os.environ.get("VACANT_RUN_PROXY") or "").rstrip("/")
    if not base:
        print("[gateshim] 沒有 $VACANT_RUN_PROXY，這一段要跑在 launcher 底下。停。",
              file=sys.stderr)
        return 2
    real = os.environ.get("VACANT_POSSESS_REAL_BIN") or real_binary(
        agent, os.environ.get("VACANT_POSSESS_SHIM_DIR"))
    if not real:
        print(f"[gateshim] 找不到真正的 {agent}。停。", file=sys.stderr)
        return 127
    # ⚠ **誠實邊界：本函式最後是 `os.execve`（行程被換掉）⇒ 它自己刪不掉這個
    #   目錄。** 刪的人是外層 `run_gate`（收尾契約第 1／2 層），撐不過 `SIGKILL`
    #   的那一份由**下一跑開場的掃地機**收（第 3 層）。所以這裡只做一件事：
    #   **確保這個目錄是「認得出來的自己人」**（父目錄固定、帶 owner 標記），
    #   否則掃地機會判成 `skipped_not_ours` 而永遠不收。
    #   代價是量出來的：codex 會把它的 plugins git repo 整個 clone 進
    #   `CODEX_HOME` ⇒ **每跑一格約 100 MB**（2026-09-20 vacant-dev 5 格 400 MB，
    #   裁決檔 `DECISION_20260919_DEFAULT_ON_INSTALL.md` §六.4-G 第 2 條）。
    _given = os.environ.get("VACANT_POSSESS_CFG")
    if _given:
        cfg = pathlib.Path(_given)
        cfg.mkdir(parents=True, exist_ok=True)
    else:
        # 直接呼叫 `--exec`（沒有外層）也要留得下標記，不然那一份沒人收
        cfg = new_cfg_dir(f"exec-{agent}")
    env = dict(os.environ)
    model = env.get("VACANT_AGENT_MODEL", "")

    if agent == "codex":
        env["CODEX_HOME"] = str(cfg)
        # ⚠ **誠實邊界：閘門這一跑預設仍然是把 codex 的牆拆掉的**
        #   （`danger-full-access`）。那是 2026-09-19／20 四個退出碼實測時的
        #   姿態，改掉預設會讓那批已歸檔的格子不可比，所以**預設沒動**。
        #   代價講明白：agent 的 shell 工具在這一跑拿得到網路 ⇒ 它可以直接
        #   `curl` 模型端點，**wire 零紀錄而收據照樣 `accepted=true`**。
        #   `VACANT_POSSESS_CODEX_SANDBOX=workspace-write` 可以關起來，
        #   而**實際用的是哪一個會逐跑落進收據**（`agent_posture`）。
        #   ⚠ 通道層（`vacant install` 寫進使用者自己那份 config.toml）
        #     已經改成預設 `workspace-write`（`possess.wire_codex`）——
        #     **兩條路的預設不一樣，不可以混講成一句。**
        sandbox = (os.environ.get("VACANT_POSSESS_CODEX_SANDBOX")
                   or "danger-full-access").strip() or "danger-full-access"
        lines = ['model_provider = "vacant"', 'approval_policy = "never"',
                 f'sandbox_mode = "{sandbox}"', "",
                 "[model_providers.vacant]", 'name = "vacant possess"',
                 f'base_url = "{base}/v1"', 'wire_api = "responses"',
                 'env_key = "OPENAI_API_KEY"']
        if model:
            lines.insert(0, f'model = "{model}"')
        (cfg / "config.toml").write_text("\n".join(lines) + "\n", "utf-8")
    elif agent == "pi":
        env["PI_CODING_AGENT_DIR"] = str(cfg)
        env.setdefault("PI_OFFLINE", "1")
        env.setdefault("PI_SKIP_VERSION_CHECK", "1")
        (cfg / "models.json").write_text(json.dumps({"providers": {"vacant": {
            "baseUrl": f"{base}/v1", "api": "openai-completions",
            "apiKey": env.get("OPENAI_API_KEY", "sk-vacant-possess"),
            "compat": {"supportsDeveloperRole": False,
                       "supportsReasoningEffort": False},
            "models": [{"id": model or "gemma-4-12b-it-qat", "name": "m",
                        "contextWindow": 262144, "maxTokens": 16384}]}}},
            ensure_ascii=False), "utf-8")
    elif agent == "opencode":
        env["OPENCODE_CONFIG_DIR"] = str(cfg)
        env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps({
            "provider": {"vacant": {
                "name": "vacant possess", "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": f"{base}/v1",
                            "apiKey": env.get("OPENAI_API_KEY",
                                              "sk-vacant-possess")},
                "models": {(model or "gemma-4-12b-it-qat"): {"name": "m"}}}},
            "permission": {"edit": "allow", "bash": "allow",
                           "webfetch": "allow"}}, ensure_ascii=False)
    elif agent == "hermes":
        env["HERMES_HOME"] = str(cfg)
        ctx = env.get("VACANT_HERMES_CONTEXT", "65536")
        (cfg / "config.yaml").write_text(
            "model:\n  provider: custom\n"
            f"  default: {model or 'gemma-4-12b-it-qat'}\n"
            f"  base_url: {base}/v1\n  context_length: {ctx}\n", "utf-8")
    elif agent == "claude":
        env["CLAUDE_CONFIG_DIR"] = str(cfg)
        for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
                  "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
                  "CLAUDE_CODE_EXECPATH", "CLAUDE_PID", "AI_AGENT",
                  "CLAUDE_CODE_USE_OPENAI"):
            env.pop(k, None)
        env["DISABLE_TELEMETRY"] = "1"
        env["DISABLE_AUTOUPDATER"] = "1"
        if model:
            env["ANTHROPIC_MODEL"] = model

    # ── 掛鉤：把這一跑的工具事件接到 Vacant 的契約上（裁決 §二 P1）────────
    #   ⚠ **裝了不等於會燒**（裁決 §三-1）。這裡只做兩件事：寫設定、
    #     把契約的環境變數交給 agent。「它到底有沒有燒」由收據端讀
    #     `hooks.jsonl` 決定（`attest.probe_framework_hook`）。
    #   `hook_install.json` 唯一的用途是分辨**「沒量到」與「量到 false」**：
    #     試過了卻連日誌都沒有 ⇒ `canary_fired=False`（降級）；
    #     根本沒試過 ⇒ `canary_fired=None`（沒量到）。
    hook_log = env.get("VACANT_HOOK_LOG")
    if hook_log:
        rep = hookcli.install(agent, cfg, hook_log=hook_log,
                              run_id=env.get("VACANT_RUN_ID", ""), proxy=base)
        try:
            pathlib.Path(hook_log).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(hook_log).with_name("hook_install.json").write_text(
                json.dumps({"attempted": rep is not None, "agent": agent,
                            "report": rep,
                            "supported": list(hookcli.INSTALLERS),
                            "note": ("`attempted` 只說我們試過，**不說它在**"
                                     "——裁決 §三-1")},
                           ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:                             # pragma: no cover
            pass
        if rep:
            env.update(rep.get("env") or {})
    try:
        os.execve(real, [real, *argv], env)
    except OSError as e:                        # pragma: no cover
        print(f"[gateshim] exec {real} 失敗：{e}", file=sys.stderr)
        return 126
    return 126                                  # pragma: no cover


def inner_posture(agent: str, argv: list[str]) -> dict:
    """**這一跑**的 agent 是在什麼沙箱／approval 姿態下跑的。

    ⚠ 回的是 `exec_inner` 實際會寫進 per-run 設定的那一份（閘門這條路），
      **不是**使用者常駐設定檔那一份（通道那條路）——兩條路的預設不一樣。
    ⚠ 量不到的欄位一律 `None`，**不准寫空字串**（鐵律 3）。
    ⚠ `flags` 只認得出 `possess.DANGER_FLAGS` 列出來的那幾個；
      **名單沒命中不等於沒有人拆牆**。
    """
    out: dict = {"layer": "gate（per-run relocate 設定）",
                 "sandbox_mode": None, "approval_policy": None,
                 "flags": possess.posture_from_argv(agent, argv)}
    if agent == "codex":
        out["sandbox_mode"] = (
            (os.environ.get("VACANT_POSSESS_CODEX_SANDBOX") or
             "danger-full-access").strip() or "danger-full-access")
        out["approval_policy"] = "never"
    elif agent == "opencode":
        out["approval_policy"] = "allow（edit/bash/webfetch，見 exec_inner）"
    else:
        out["note"] = ("這個 agent 的 per-run 設定沒有沙箱欄位 ⇒ 沒量到"
                       "（不是「沒有沙箱」）")
    return out


# ── 外層：shim 呼叫的那一段 ────────────────────────────────────────────

def run_gate(agent: str, argv: list[str]) -> int:
    shim_dir = os.environ.get("VACANT_POSSESS_SHIM_DIR")
    real = real_binary(agent, shim_dir)
    if real is None:
        print(f"[vacant] 找不到真正的 {agent}（shim 目錄已從 PATH 排除）。",
              file=sys.stderr)
        return 127
    if os.environ.get("VACANT_POSSESS_BYPASS") in ("1", "true", "yes") or \
            is_passthrough(agent, argv):
        # ⚠ **明示的繞過路**：透傳，不 gate。通道層仍然是使用者自己那份
        #   常駐設定（也就是常駐 proxy），所以模型呼叫照樣被中介。
        return subprocess.run([real, *argv]).returncode

    cwd = pathlib.Path.cwd()
    suite, suite_source = resolve_suite(cwd)
    task_id = f"possess_{agent}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    run_dir = pathlib.Path.home() / ".vacant-run" / task_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # ── 收尾契約第 3 層：**開場先收上一次被 kill -9 留下來的** ──────────
    #   放在開場而不是收尾，理由是它要收的正是「收尾沒機會跑」的那一種。
    sweep = sweep_cfg_dirs()
    # ── 收尾契約第 1 層：這一跑自己的目錄，外層建、外層刪 ───────────────
    #   內層（`--exec`）是 `os.execve`，它自己沒有機會刪 ⇒ 名字必須由外層決定。
    own_cfg: pathlib.Path | None = None
    if not os.environ.get("VACANT_POSSESS_CFG"):
        own_cfg = new_cfg_dir(f"run-{agent}")
        os.environ["VACANT_POSSESS_CFG"] = str(own_cfg)

    # `--suite` 不可以在工作區底下（launcher 的擋門：agent 改得到的驗收不是
    # 驗收）。自動找到的那一份多半就在專案裡 ⇒ **複製一份到工作區外**，
    # 權威的是複製出來的這一份。
    suite_arg = None
    if suite is not None:
        suite_arg = run_dir / "suite"
        shutil.copytree(suite, suite_arg, dirs_exist_ok=True)

    # ⚠ **閘門那一跑用的是它自己的 ephemeral proxy，不是常駐那一支**
    #   （收據的 wire log 才對得起來）。但 `launcher` 是從環境變數推上游的，
    #   而使用者的 shell 裡通常什麼都沒有 ⇒ 會落到 `SINK_UPSTREAM`、
    #   每一通都被擋在本機。**上游要從 install 當時記下來的 state 補進去。**
    #   沒有 state（沒裝過、直接跑 gateshim）就維持原樣＝fail-closed。
    _inject_upstreams_from_state()

    # ── 掛鉤契約的環境：內層 `--exec` 讀得到，它才裝得起來 ────────────────
    #   ⚠ 只是「把契約的位置講清楚」，**不是**宣稱掛鉤會燒。
    os.environ["VACANT_HOOK_LOG"] = str(run_dir / "hooks.jsonl")
    os.environ["VACANT_RUN_ID"] = task_id
    os.environ["VACANT_HOOK_AGENT"] = agent

    inner = [sys.executable, "-m", "vacant_network.vrun.gateshim", "--exec",
             agent, *argv]
    os.environ["VACANT_POSSESS_REAL_BIN"] = real
    # ── 收尾契約第 2 層：溫和的終止也要走到 `finally` ────────────────────
    #   `SIGTERM`（systemd stop／`kill`）與 `SIGHUP`（終端機關掉）的預設動作是
    #   **直接終止行程，`finally` 不會跑**。換成丟 `SystemExit` 就會正常解堆疊。
    #   ⚠ `SIGKILL` 攔不到，那一格交給第 3 層（下一跑的掃地機）。
    #   ⚠ `SIGINT` 維持預設（`KeyboardInterrupt` 本來就會走 `finally`）。
    def _sig(signum, _frame):               # pragma: no cover - 訊號路徑
        raise SystemExit(128 + signum)
    for _s in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(_s, _sig)
        except (OSError, ValueError, AttributeError):   # pragma: no cover
            pass
    try:
        summary = launcher.run(
            inner, workspace=cwd, run_dir=run_dir, suite_dir=suite_arg,
            vacant_on=True, task_id=task_id, sandbox_name="none",
            allow_no_suite=(suite_arg is None),
            test_timeout_s=float(os.environ.get("VACANT_TEST_TIMEOUT", "30")),
            inherit_stdin=sys.stdin.isatty(),
        )
    finally:
        cleanup = release_cfg_dir(own_cfg)
        if cleanup.get("owned") and not cleanup.get("ok"):
            # ⚠ 不 raise、不靜默：**退出碼不受影響**（磁碟沒清乾淨不是裁決），
            #   但一定要印出來，而且 owner 標記已被改寫成死的交給下一次掃地機。
            print(f"[vacant] ⚠ per-run 設定目錄刪不掉：{cleanup.get('path')}"
                  f"（{cleanup.get('error')}）——已標記交給下一次掃地機。",
                  file=sys.stderr)
    rs = int(summary.get("requests_seen") or 0)
    possess.mark_proven(agent, rs)
    verdict = launcher.exit_code(summary)
    if summary.get("stop_reason") == "ungated":
        verdict = EXIT_UNGATED
    rs0_mode = os.environ.get("VACANT_POSSESS_RS0", "fail")
    if rs == 0 and verdict != launcher.EXIT_VOID:
        print("[vacant] ⚠ requests_seen = 0：這一跑**沒有任何模型呼叫經過 "
              "proxy**。那一格在收據上跟一個合法的拒交格只差這一個欄位，"
              "所以裁決不可歸因。", file=sys.stderr)
        if rs0_mode not in ("warn", "0", "off"):
            verdict = EXIT_NO_MEDIATION

    # ── 認證：這一跑有沒有在圍牆裡跑過、工具事件對不對得上 ────────────────
    #   ⚠ 這一段與上面的裁決**正交**：它回答的不是「交付還是拒交」，
    #     而是「這張收據能不能拿來究責」。
    a_mode = attest_mode()
    # ⚠ **這一份是 `launcher` 量的、而且已經簽進鏈了**（`ws_verdict` 的
    #   `tier`／`attested`／`attestation_sha256`）。本層不重算——重算會得到
    #   一份跟鏈上那個雜湊對不起來的第二版本，而「兩份都自稱是這一跑的認證」
    #   正是收據最不該有的東西。
    #   ⚠ **不可以在這裡改寫它任何一個欄位**：鏈上那個 `attestation_sha256`
    #     是對這一份的雜湊，動一個字就對不上了。
    attestation: dict | None = summary.get("attestation")
    if a_mode != "off" and attestation is not None:
        if not attestation.get("attested"):
            print(f"[vacant] ⚠ 未認證（tier {attestation.get('tier')}）："
                  f"{attestation.get('tier_sentence') or attestation.get('error')}",
                  file=sys.stderr)
            for r in attestation.get("tier_reasons") or []:
                print(f"[vacant]   · {r}", file=sys.stderr)
        verdict = apply_tier_exit(verdict, attestation.get("tier"), a_mode)

    extra = {
        "possess_agent": agent, "suite_source": suite_source,
        "suite_dir": str(suite) if suite else None,
        "gate": "ran" if suite_arg is not None else "skipped",
        "requests_seen": rs, "stop_reason": summary.get("stop_reason"),
        "accepted": summary.get("accepted"), "shim_exit": verdict,
        "argv": argv, "real_binary": real, "cwd": str(cwd),
        # per-run 設定目錄的收尾：開場掃了什麼、收尾刪了什麼、有沒有刪不掉的
        "cfg_sweep": sweep, "cfg_cleanup": cleanup,
        # ⚠ **這一跑的 agent 是在什麼防護姿態下跑的。**
        #   沒有這一欄，一個 `workspace-write` 下的 `accepted=true` 跟一個
        #   `danger-full-access` 下的 `accepted=true` 在收據上長得一模一樣
        #   ——那正是 A 類假拒交那四格的病。讀不出來寫 `null`，不寫空字串。
        "agent_posture": inner_posture(agent, argv),
        # ⚠ **這一跑有沒有在圍牆裡跑過**（裁決 §二 P0）。`attest_mode=off`
        #   之下是 `null` ＝**沒量到**，不是「量到沒有」（鐵律 3）。
        "attestation": attestation,
        "attest_mode": a_mode,
        "tier": (attestation or {}).get("tier"),
        "attested": (attestation or {}).get("attested"),
    }
    # ── C 級不發收據（裁決 §三-2）────────────────────────────────────────
    #   「意思不明的收據比沒有更糟：它會讓『拒交』與『沒跑過』長得一樣。」
    #   ⚠ 所以拒發的時候要落一份**長得不像收據**的東西，而且檔名就說它不是。
    #     兩件事都要：`possess.json` **不存在**（下游拿不到一張弱收據），
    #     `NOT_CERTIFIED.json` 存在（「拒發」與「這一跑沒發生」分得開）。
    if (a_mode == "fail" and attestation is not None
            and attestation.get("tier") == attest.TIER_C):
        (run_dir / "NOT_CERTIFIED.json").write_text(json.dumps({
            "not_a_receipt": True,
            "why": ("C 級＝既沒有圍牆也沒有掛鉤 ⇒ 這一跑的紀錄不足以究責。"
                    "發一張弱收據會讓「拒交」與「沒跑過」長得一樣，"
                    "那正是繞過壓測 A 類那四格的病（裁決 §三-2）。"),
            "tier": attestation.get("tier"),
            "tier_reasons": attestation.get("tier_reasons"),
            "attestation": attestation,
            "possess_json_written": False,
            "diagnostics": {k: extra[k] for k in
                            ("possess_agent", "suite_source", "requests_seen",
                             "stop_reason", "shim_exit", "cwd")},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[vacant] ⛔ C 級 ⇒ **拒發收據**。"
              f"（{run_dir / 'NOT_CERTIFIED.json'}）", file=sys.stderr)
    else:
        (run_dir / "possess.json").write_text(
            json.dumps(extra, ensure_ascii=False, indent=2), encoding="utf-8")
    mark = {0: "交付", 20: "拒交", EXIT_UNGATED: "**沒有閘門（只中介）**",
            launcher.EXIT_VOID: "infra_void",
            EXIT_NO_MEDIATION: "**沒量到中介**",
            EXIT_TIER_B: "**B 級（工具層未閘門）**",
            EXIT_TIER_B_PRIME: "**B′ 級（模型通道沒看全）**",
            EXIT_TIER_C: "**C 級（未受控，拒發收據）**"}.get(verdict, str(verdict))
    tier_mark = (f"　級別 {attestation.get('tier')}" if attestation else "")
    print(f"[vacant] {agent}　{mark}　驗收來源 {suite_source}　"
          f"wire {rs} 通{tier_mark}　收據 {run_dir}", file=sys.stderr)
    return verdict


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] == ["--exec"]:
        return exec_inner(a[1], a[2:])
    if a[:1] == ["--sweep"]:
        # 手動掃地（`uninstall` 也會呼叫這一支）。`--sweep-now` ＝ 不管歲數，
        # 只要擁有者死了就收——**收工用**，不是預設。
        rep = sweep_cfg_dirs(max_age_s=0.0 if "--sweep-now" in a else None)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if not rep["failed"] else 1
    if not a:
        print("用法：gateshim <agent> [agent 的參數…]｜--sweep [--sweep-now]",
              file=sys.stderr)
        return 2
    return run_gate(a[0], a[1:])


if __name__ == "__main__":
    raise SystemExit(main())
