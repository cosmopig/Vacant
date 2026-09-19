"""這支在架構裡承重什麼：**收據上那一句「這一跑有沒有在圍牆裡跑過」**。

`DECISION_20260920_COMPLETE_MEDIATION.md` §二 P0 的另一半。機制那一半
（enclosure ＝ netns ＋ mount ns ＋ 一扇門）已經量完並落盤，但**收據上一個
欄位都沒有** ⇒ 拿到一張收據的人看不出那一跑是不是在圍牆裡跑的 ⇒
「每一次都經過 Vacant」這句新口徑**現在還不能講**。本檔補的就是那些欄位。

## 四個欄位（裁決 §二 P0 逐字）

    enclosure     { ns_id, policy_sha256, applied }
    framework_hook{ agent, contract_version, canary_fired }
    reconciled    { relay_calls, hook_events, unexplained }
    tier          A / B / B' / C

## 分級（裁決 §三。**展場只允許 A 級**）

| 級 | 條件 | 收據能說的話 | 退出碼 |
|---|---|---|---|
| A  | enclosure 成立 ＋ canary 有燒 ＋ `unexplained == 0` | 每一通模型呼叫都經過 Vacant，且都對得上一個工具事件 | 0／20／21 既有語意 |
| B  | enclosure 成立、無掛鉤 | 每一個離開的位元組都留下紀錄；**分不出哪通是模型叫的、哪通是框架自己叫的** | `gateshim.EXIT_TIER_B`＝24 |
| B' | 模型通道不在（或不完整在）Vacant 眼前，但工具層有紀錄 | 工具層每次有紀錄；**模型通道 Vacant 沒（完整）看到** | `EXIT_TIER_B_PRIME`＝25 |
| C  | 兩者皆無 | **拒發收據**，不是發一張弱的 | `EXIT_TIER_C`＝26 |

⚠ **B' 在本檔比裁決表格多涵蓋一格，那是刻意的**：裁決只寫「行程內模型」。
  但「掛鉤燒了、圍牆沒套、模型走網路」這一格在表格上無處可去——它**有**
  工具層紀錄，把它判成 C（拒發收據）等於丟掉真的量到的東西。所以本檔把 B'
  定義成「**工具層有紀錄、但模型通道不保證全部經過 Vacant**」，並用
  `b_prime_kind` 分開 `in_process_model` 與 `channel_not_enclosed` 兩種來源。
  兩者的退出碼相同（都不是 0），但收據上的句子不一樣。

## 三條紀律（裁決 §三，每一條在本檔都有可執行的對應物）

1. **級別由探針決定，不准用「我們裝過了」推論「它在」。**
   `probe_enclosure()` 量的是**這個行程現在有幾張網路介面**與
   **netns 是不是跟圍牆外面那一個不同**，不是「我有沒有打 `--unshare-all`」。
   `probe_framework_hook()` 讀的是**掛鉤自己寫下來的那一行**，
   `contract_version` 也是從那一行讀出來的，**不是**本檔的常數。
   ⚠ 這條紀律是被兩件實測逼出來的：
   · Linux 上 `install-status` 印「✓ 已寫入」而 codex 其實起不來；
   · Codex 的啟動橫幅在 requirements 強制 proxy 生效時**照樣印**
     `(network access enabled)` ⇒ **橫幅會說謊，不要讀橫幅**。
2. **C 級不發收據。** 意思不明的收據比沒有更糟：它會讓「拒交」與「沒跑過」
   長得一樣——那正是繞過壓測 A 類那四格的病（真拒交與假拒交只差
   `requests_seen` 一欄）。
3. **展場只允許 A 級**（`VACANT_ATTEST=fail` ＋ `VACANT_TIER_REQUIRED=A`）。

## 鐵律 3 在本檔是型別層的規格，不是註解

**「沒量到」≠「量到 0」。** 每一個欄位都是三態：

    True / False / None          成立 / 不成立 / **沒量到**
    int  / int   / None          量到的數 / 量到的數 / **沒量到**

`None` 絕對不可以用 `False` 或 `0` 代替，反之亦然。本檔所有 `*_n` 欄位在
沒量到的時候是 `None`；`unexplained` 沒量到的時候是 `None`，而
`unexplained is None` **不會**滿足 A 級（A 要 `== 0`）。
`assert_three_state()` 是這條的可執行防呆，`selftest()` 會跑它。

## 兩種用法：`--probe`（圍牆裡面）／`--assemble`（主機上）

圍牆外面的主機**看不到**圍牆裡面的 netns，圍牆裡面的行程**看不到**主機上
那份 journal（門的 journal 落在主機側）。所以量測分兩段：

    圍牆內：python3 -m vacant_network.vrun.attest --probe   > probe.json
    主機上：python3 -m vacant_network.vrun.attest --assemble \
                --probe-json probe.json --relay-index <門的 index.jsonl> \
                --relay-since N --hook-log <workspace>/.vacant-hooks.jsonl \
                --run-id <id> --agent <name>

`gateshim` 那條路（launcher 自己起的 ephemeral proxy）兩段都在同一個行程裡，
直接呼叫 `attest()` 即可。

## 誠實邊界（改碼請保留，每一條都是量出來的或推得出來的）

1. **`applied=True` 說的是「這個行程只有 loopback 一張介面」**，不是
   「這台機器上不存在別的路」。一台本來就只有 `lo` 的機器（極簡容器）
   會被讀成成立。所以 `ns_id` 與 `outer_ns_id` 兩欄要一起看：
   `ns_differs_from_outer is True` 才是**硬證據**。
2. **探針防的是「我們自己的量具說謊」，不是「agent 偽造探針輸出」。**
   探針跑在 agent 之前、跟 agent 同一個 namespace，但輸出經過共用的
   workspace／stdout ⇒ 一個惡意 agent 事後改得掉那個檔。要擋那一層得靠
   **主機側**從 `/proc/<pid>/ns/net` 自己讀（`--host-ns-of-pid`）。
   兩者都給，但不可以混講成一句。
3. **對帳是「通數與次序」的對帳，不是「身分」的對帳。**
   `unexplained` 的判準是「這一通模型呼叫之前，有沒有一個還沒被消耗掉的
   工具／提示事件」。它抓得到「沒有任何工具事件卻多出一通」（框架自己叫的、
   或有人直接對門 `curl`），抓不到「在一個合法的回合視窗裡多塞一通」。
4. **`canary_fired=True` 只證明掛鉤這一次燒了**，不證明它下一次還在
   （`--bare`、`disableAllHooks`、Codex 的 `trusted_hash` 改一個空白就
   fail-silent；`DECISION_20260920_AGENT_HOOKS_MEASURED.md`）。這正是裁決
   §二「kernel 給『有沒有』（保證），hook 給『是什麼』（語意）」的理由。
5. **`tier` 是這一跑的級別，不是這個 agent 的級別。** 同一個 agent 換一台
   機器就換一級——級別是平台的屬性（裁決 §三）。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import socket
import sys
import time
from typing import Any

#: 掛鉤契約版本。**`framework_hook.contract_version` 不是從這裡讀的**——
#: 那一欄要讀掛鉤**自己寫下來的那一行**，否則就變成「我們裝過了」推論。
#: 這個常數只有兩個用途：`hookcli` 寫進事件、以及對帳時比對版本有沒有漂。
CONTRACT_VERSION = "vacant-hook/1"

#: 掛鉤事件裡「開了一個回合」的那幾種——一個回合開了才輪得到一通模型呼叫。
#: `canary` 也算：它自己就會打一通（見 `hookcli`），那一通要對得上。
#:
#: ⚠ **`session_start` 刻意不在名單上。** 它不會自己引起一通模型呼叫
#:   （引起第一通的是 `user_prompt_submit`）。把它算進來會多出一個
#:   「空的回合額度」，於是一通**多出來的**呼叫就被它吸收掉——
#:   2026-09-20 在 vacant-dev 上實測到這個假陰性：rogue 那一格真的多打了一通，
#:   而對帳卻回 `unexplained=0`。**負控制抓到的就是這個。**
#: ⚠ 代價要講明白：沒有 `user_prompt_submit` 這一類事件的框架
#:   （例如 OpenCode 的 plugin API）**第一通會對不上** ⇒ 那個 agent 在
#:   補上對應事件之前到不了 A 級。那是誠實的結果，不是要繞過去的麻煩。
TURN_OPENING_EVENTS = ("canary", "user_prompt_submit",
                       "post_tool_use", "tool_result")

#: canary 那一通在門的 journal 裡長什麼樣（`hookcli` 打的就是這一條）。
CANARY_PATH = "/v1/models"
CANARY_QUERY_KEY = "vacant_canary"

#: 圍牆裡面那份政策檔的預設位置（`enc.sh` 把門的目錄 `--ro-bind` 到 `/run/vacant`）。
DEFAULT_POLICY_PATH = "/run/vacant/policy.json"
DEFAULT_DOOR_SOCK = "/run/vacant/relay.sock"

#: 分級的四個標籤。**逐字凍結**（收據欄位、退出碼對照表、測試都引用這裡）。
TIER_A, TIER_B, TIER_B_PRIME, TIER_C = "A", "B", "B'", "C"


# ── 鐵律 3 的可執行防呆 ────────────────────────────────────────────────

def assert_three_state(block: dict, fields: tuple[str, ...],
                       *, label: str = "") -> None:
    """三態欄位不准用 `0`／`""` 冒充 `None`，也不准用 `None` 冒充 `False`。

    這是鐵律 3 的可執行版本。擋得住的是**型別層的偷換**：

      · `False` 出現在一個只准 `True/None` 的位置——不擋（那是語意，不是型別）；
      · `0` 出現在一個布林三態欄位 ⇒ **炸**（`0` 讀起來像「量到零」，
        但布林欄位的「量到零」應該寫 `False`）；
      · 欄位**不存在** ⇒ **炸**（缺欄位跟 `None` 在 JSON 裡長得一樣，
        但在讀的人眼裡「這個欄位還沒做」跟「這一跑沒量到」是兩件事）。

    ⚠ 只檢查布林三態。數字三態（`relay_calls` 之類）由
      `assert_count_three_state()` 檢查。
    """
    for f in fields:
        if f not in block:
            raise ValueError(f"{label}{f} 欄位不存在——缺欄位不是「沒量到」，"
                             f"「沒量到」要明寫 null（鐵律 3）")
        v = block[f]
        if v is None or v is True or v is False:
            continue
        raise ValueError(
            f"{label}{f}={v!r}（{type(v).__name__}）——這一欄只准 "
            f"True／False／None 三態；用 {v!r} 表達狀態會讓「沒量到」與"
            f"「量到 0」長得一樣（鐵律 3）")


def assert_count_three_state(block: dict, fields: tuple[str, ...],
                             *, label: str = "") -> None:
    """數字三態：`int`（量到了，值可以是 0）或 `None`（**沒量到**）。

    ⚠ `bool` 是 `int` 的子類 ⇒ 這裡要先把 `bool` 踢掉，否則一個寫錯型別的
      `relay_calls: false` 會被讀成「0 通」而不是「這個欄位壞了」。
      這個坑 `verify_receipts.mediation_of` 已經踩過一次，逐字沿用它的守法。
    """
    for f in fields:
        if f not in block:
            raise ValueError(f"{label}{f} 欄位不存在（鐵律 3）")
        v = block[f]
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(
                f"{label}{f}={v!r}（{type(v).__name__}）——這一欄只准 int 或 "
                f"None（沒量到）。bool 會被讀成 0／1 而那是另一件事")


# ── 1. enclosure 探針（跑在**圍牆裡面**，跟 agent 同一個 namespace）────

def _net_ns_id() -> str | None:
    """這個行程的 network namespace id，例如 `net:[4026532567]`。

    回 `None` ＝ **這台機器上問不出來**（macOS 沒有 `/proc`），
    **不是**「沒有 namespace」。鐵律 3。
    """
    try:
        return os.readlink("/proc/self/ns/net")
    except OSError:
        return None


def _interfaces() -> list[str] | None:
    """這個行程看得到的網路介面名。`None` ＝ 問不出來。

    這一欄是 `applied` 的主要依據，理由是它**不需要送出任何一個位元組**
    就量得到「有沒有別的路」：`bwrap --unshare-all` 之下新的 netns 裡只有
    `lo`。用「連連看某個目標」來量會反過來——負控制那一格會真的出網。
    """
    try:
        return sorted({name for _idx, name in socket.if_nameindex()})
    except (OSError, AttributeError):       # pragma: no cover - 平台差異
        return None


def _door_reachable(sock_path: str | None) -> bool | None:
    """門**活著嗎**——真的連一次，不是看 socket 檔在不在。

    ⚠ `[ -S socket ]` ≠ 門活著：2026-09-20 實測過，前一格的 proxyd 收到
      SIGTERM 之後還沒 unlink，下一格用 `-S` 判成「門已經在了」⇒ 不起自己的
      門 ⇒ 圍牆裡一路 `FileNotFoundError` 而退出碼還是 0。

    回 `None` ＝ 沒給路徑（沒量到）；`False` ＝ 給了路徑但連不上。
    """
    if not sock_path:
        return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(sock_path)
        s.close()
        return True
    except OSError:
        return False
    except (AttributeError, ValueError):    # pragma: no cover - 平台沒有 AF_UNIX
        return None


def _sha256_file(p: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def probe_enclosure(*, policy_path: str | os.PathLike | None = None,
                    door_sock: str | None = None) -> dict:
    """**量**這個行程在不在圍牆裡。回 `enclosure` 那一塊。

    判準（三態，缺一不可）：

      `applied=None`   介面問不出來而且 netns 也問不出來 ⇒ **沒量到**。
      `applied=False`  量到了，而且**看得到 loopback 以外的介面**
                       （或 netns 跟圍牆外面那一個相同）⇒ 不在圍牆裡。
      `applied=True`   量到了，而且**只有 loopback**。

    ⚠ 誠實邊界 1（模組 docstring）：「只有 lo」是 netns 隔離的證據，不是
      「這台機器上不存在別的路」的證明。`ns_differs_from_outer is True`
      才是硬證據，而它需要政策檔裡有 `outer_net_ns`（`enc.sh` 會寫）。
    """
    policy_p = pathlib.Path(policy_path or
                            os.environ.get("VACANT_ENCLOSURE_POLICY") or
                            DEFAULT_POLICY_PATH)
    policy_sha = _sha256_file(policy_p) if policy_p.is_file() else None
    policy: dict = {}
    if policy_sha is not None:
        try:
            policy = json.loads(policy_p.read_text("utf-8"))
        except (OSError, ValueError):
            policy = {}
    ns_id = _net_ns_id()
    ifaces = _interfaces()
    outer = policy.get("outer_net_ns") or os.environ.get(
        "VACANT_ENCLOSURE_OUTER_NS") or None
    ns_differs: bool | None = None
    if ns_id is not None and outer:
        ns_differs = (ns_id != outer)
    sock = (door_sock or policy.get("door_sock")
            or os.environ.get("VACANT_ENCLOSURE_DOOR_SOCK")
            or (DEFAULT_DOOR_SOCK if policy_sha is not None else None))

    applied: bool | None
    reason: str
    if ifaces is None and ns_id is None:
        applied, reason = None, "介面與 netns 都問不出來 ⇒ 沒量到（不是「沒有圍牆」）"
    elif ns_differs is False:
        # 硬否證：netns 跟圍牆外面**同一個** ⇒ 不管幾張介面都不算在圍牆裡
        applied, reason = False, "netns 與圍牆外面相同 ⇒ 沒有進到新的 network namespace"
    elif ifaces is None:
        applied, reason = None, "netns 問得出來但介面問不出來 ⇒ 判不了（沒量到）"
    elif set(ifaces) - {"lo"}:
        applied, reason = False, f"看得到 loopback 以外的介面 {sorted(set(ifaces) - {'lo'})} ⇒ 有別的路"
    else:
        applied = True
        reason = ("只有 loopback 一張介面"
                  + ("，而且 netns 與圍牆外面不同（硬證據）" if ns_differs
                     else "；⚠ 沒有 outer_net_ns 可比對 ⇒ 證據較弱，見誠實邊界 1"))
    out = {
        "applied": applied,
        "ns_id": ns_id,
        "policy_sha256": policy_sha,
        "probe": {
            "method": "if_nameindex + /proc/self/ns/net（零位元組出網）",
            "interfaces": ifaces,
            "outer_net_ns": outer,
            "ns_differs_from_outer": ns_differs,
            "policy_path": str(policy_p),
            "policy_present": policy_sha is not None,
            "door_sock": sock,
            "door_reachable": _door_reachable(sock),
            "reason": reason,
            "probed_at": time.time(),
            "probed_by_pid": os.getpid(),
        },
    }
    assert_three_state(out, ("applied",), label="enclosure.")
    return out


def host_ns_of_pid(pid: int) -> str | None:
    """**主機側**從 `/proc/<pid>/ns/net` 讀那個行程的 netns（誠實邊界 2）。

    圍牆裡的探針防的是「我們自己的量具說謊」；這一支防的是「圍牆裡的東西
    偽造探針輸出」——它讀的是 kernel，不經過圍牆裡任何人的手。

    回 `None` ＝ 讀不到（沒有 `/proc`、行程已結束、權限不足）＝**沒量到**。
    """
    try:
        return os.readlink(f"/proc/{int(pid)}/ns/net")
    except (OSError, TypeError, ValueError):
        return None


# ── 2. 框架掛鉤探針（讀掛鉤**自己寫下來的那一行**）────────────────────

def read_hook_events(hook_log: str | os.PathLike | None,
                     *, run_id: str | None = None) -> list[dict] | None:
    """讀掛鉤日誌。`None` ＝ **沒有這份日誌**（沒量到），`[]` ＝ 有檔但零事件。

    ⚠ 這兩者差很多：沒有檔 ＝ 掛鉤從頭到尾沒被呼叫過（或我們根本沒裝）；
      有檔但零事件 ＝ 有人建了檔卻沒有任何事件，那是壞掉不是沒裝。
    """
    if not hook_log:
        return None
    p = pathlib.Path(hook_log)
    if not p.is_file():
        return None
    out: list[dict] = []
    try:
        for line in p.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                out.append({"event": "_unparsable", "raw": line[:200]})
                continue
            if run_id and rec.get("run_id") not in (None, run_id):
                continue
            out.append(rec)
    except OSError:
        return None
    return out


def probe_framework_hook(*, agent: str | None,
                         hook_log: str | os.PathLike | None,
                         run_id: str | None = None,
                         install_attempted: bool | None = None) -> dict:
    """回 `framework_hook` 那一塊。**`canary_fired` 由日誌決定，不由安裝決定。**

      `canary_fired=None`   我們沒有裝掛鉤（`install_attempted` 不為 True）
                            而且日誌不存在 ⇒ **沒量到**。
      `canary_fired=False`  裝了（或日誌存在），但**那一行不在** ⇒ 掛鉤沒燒。
                            這正是 Linux 上 `install-status` 說「✓ 已寫入」
                            而 codex 其實起不來的那一格——**自動降級**。
      `canary_fired=True`   日誌裡有這一跑的 `canary` 事件。

    ⚠ `contract_version` 讀的是**那一行自己帶的版本**。日誌裡的版本跟本檔的
      `CONTRACT_VERSION` 不同 ⇒ 照實記下來並在 `version_drift` 標記，
      **不改寫成我們期待的那個**。
    """
    events = read_hook_events(hook_log, run_id=run_id)
    out: dict[str, Any] = {
        "agent": agent or None,
        "contract_version": None,
        "canary_fired": None,
        "events_n": None if events is None else len(events),
        "log": str(hook_log) if hook_log else None,
        "install_attempted": install_attempted,
        "version_drift": None,
        "reason": "",
    }
    if events is None:
        if install_attempted is True:
            # 裝了、卻連日誌都沒有 ⇒ **量到了，而且是假的**（不是沒量到）
            out["canary_fired"] = False
            out["reason"] = ("宣稱裝過掛鉤，但掛鉤日誌根本不存在 ⇒ 掛鉤沒跑。"
                             "⚠ 這就是 `install-status` 說「✓ 已寫入」而它其實"
                             "起不來的那一格——不准用安裝推論存在。")
        else:
            out["reason"] = "沒有掛鉤日誌，而且沒宣稱裝過 ⇒ 沒量到（不是「沒有掛鉤」）"
        assert_three_state(out, ("canary_fired",), label="framework_hook.")
        return out
    canaries = [e for e in events if e.get("event") == "canary"]
    out["canary_fired"] = bool(canaries)
    if canaries:
        ver = canaries[0].get("contract")
        out["contract_version"] = ver if isinstance(ver, str) else None
        out["version_drift"] = (out["contract_version"] != CONTRACT_VERSION)
        out["reason"] = f"掛鉤日誌裡有 {len(canaries)} 筆 canary ⇒ 掛鉤真的燒了"
        if canaries[0].get("agent") and not out["agent"]:
            out["agent"] = canaries[0]["agent"]
    else:
        out["reason"] = (f"掛鉤日誌在（{len(events)} 筆事件）但**沒有 canary** "
                         f"⇒ 這一跑的掛鉤沒有在 session 開頭燒起來 ⇒ 降級")
    assert_three_state(out, ("canary_fired",), label="framework_hook.")
    return out


# ── 3. 對帳（中繼看到的通數 vs 掛鉤事件）──────────────────────────────

def read_relay_calls(index_path: str | os.PathLike | None,
                     *, since: int = 0) -> list[dict] | None:
    """讀門／proxy 的 journal（`wire/index.jsonl`）。`None` ＝ 沒量到。

    `since` ＝ 這一跑開始之前那份 journal 已經有幾行（門是常駐的話前面會有
    別人的通數）。**由呼叫端數，不是本檔猜。**
    """
    if not index_path:
        return None
    p = pathlib.Path(index_path)
    if not p.is_file():
        return None
    try:
        lines = p.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    out: list[dict] = []
    for line in lines[int(since):]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            out.append({"_unparsable": line[:200]})
    return out


def _is_canary_call(rec: dict, run_id: str | None) -> bool:
    path = str(rec.get("path") or "")
    if CANARY_QUERY_KEY not in path:
        return False
    if run_id and run_id not in path:
        return False
    return True


def reconcile(*, relay_calls: list[dict] | None,
              hook_events: list[dict] | None,
              run_id: str | None = None) -> dict:
    """回 `reconciled` 那一塊：中繼看到的通數與掛鉤事件對不對得起來。

    判準（誠實邊界 3）：**一通模型呼叫要對得上一個「還沒被消耗掉的回合開端」**
    （`TURN_OPENING_EVENTS`，時間在它之前）。貪婪地依時間配對，配不到的就是
    `unexplained`。

      `unexplained=None`  兩邊有任一邊沒量到 ⇒ **沒量到**（不是 0！）。
                          A 級要 `== 0`，所以「沒量到」自動達不到 A 級。
      `unexplained=0`     每一通都對得上。
      `unexplained>0`     有通數對不上 ⇒ 降級。

    ⚠ 它抓得到「沒有任何工具事件卻多出一通」（框架自己叫的、或有人直接對門
      `curl`），抓不到「在一個合法的回合視窗裡多塞一通」。
    """
    out: dict[str, Any] = {
        "relay_calls": None, "hook_events": None, "unexplained": None,
        "canary_calls": None, "refused_path": None,
        "unexplained_detail": None,
        "method": ("貪婪時間配對：一通模型呼叫要對得上一個還沒被消耗掉的"
                   "回合開端事件（" + "／".join(TURN_OPENING_EVENTS) + "）。"
                   "⚠ `session_start` **刻意不算**——它不會自己引起一通呼叫，"
                   "算進來會讓多出來的那一通被一個空額度吸收掉"),
        "reason": "",
    }
    if relay_calls is None:
        out["reason"] = "沒有中繼 journal ⇒ 沒量到（不是「零通」）"
    if hook_events is None:
        out["reason"] = ((out["reason"] + "；") if out["reason"] else "") + \
            "沒有掛鉤日誌 ⇒ 對不了帳（不是「零事件」）"
    if relay_calls is not None:
        out["relay_calls"] = len(relay_calls)
        out["canary_calls"] = sum(1 for r in relay_calls
                                  if _is_canary_call(r, run_id))
        out["refused_path"] = sum(1 for r in relay_calls
                                  if r.get("refused_path"))
    if hook_events is not None:
        out["hook_events"] = len(hook_events)
    if relay_calls is None or hook_events is None:
        assert_count_three_state(
            out, ("relay_calls", "hook_events", "unexplained"),
            label="reconciled.")
        return out

    opens = sorted(
        (float(e.get("ts") or 0.0) for e in hook_events
         if e.get("event") in TURN_OPENING_EVENTS),
    )
    calls = sorted(relay_calls, key=lambda r: float(r.get("ts") or 0.0))
    used = 0
    unexplained: list[dict] = []
    for c in calls:
        t = float(c.get("ts") or 0.0)
        # 還沒被消耗掉、而且時間在這一通之前的第一個回合開端
        if used < len(opens) and opens[used] <= t:
            used += 1
            continue
        unexplained.append({"call_id": c.get("call_id"),
                            "path": c.get("path"), "ts": c.get("ts"),
                            "status": c.get("status")})
    out["unexplained"] = len(unexplained)
    out["unexplained_detail"] = unexplained or []
    out["reason"] = (
        f"{out['relay_calls']} 通中繼、{len(opens)} 個回合開端事件 ⇒ "
        f"{out['unexplained']} 通對不上")
    assert_count_three_state(
        out, ("relay_calls", "hook_events", "unexplained"),
        label="reconciled.")
    return out


# ── 4. 分級 ────────────────────────────────────────────────────────────

#: 每一級在收據上**能說的那句話**。逐字凍結——展場牆上印的就是這幾句。
TIER_SENTENCE = {
    TIER_A: "每一通模型呼叫都經過 Vacant，且都對得上一個工具事件。",
    TIER_B: ("每一個離開這個行程的位元組都留下紀錄；"
             "**但分不出哪一通是模型叫的、哪一通是框架自己叫的**。"),
    TIER_B_PRIME: ("工具層每一次都有紀錄；"
                   "**模型通道 Vacant 沒有（完整）看到**。"),
    TIER_C: "**未認證**：既沒有圍牆也沒有掛鉤 ⇒ 這一跑不發收據。",
}


def grade(enclosure: dict, framework_hook: dict, reconciled: dict,
          *, in_process_model: bool | None = None) -> dict:
    """三塊量測 ⇒ 一個級別。**級別是量出來的，不是宣告的**（裁決 §三-1）。"""
    enc_ok = enclosure.get("applied") is True
    hook_ok = framework_hook.get("canary_fired") is True
    recon_ok = reconciled.get("unexplained") == 0      # None 不滿足（鐵律 3）
    reasons: list[str] = []

    if enc_ok and hook_ok and recon_ok:
        tier, kind = TIER_A, None
        reasons.append("圍牆成立 ＋ 掛鉤 canary 有燒 ＋ 每一通都對得上")
    elif enc_ok and hook_ok and not recon_ok:
        tier, kind = TIER_B, None
        reasons.append(
            "圍牆成立、掛鉤也燒了，**但對帳沒過**"
            f"（unexplained={reconciled.get('unexplained')!r}）⇒ 降到 B："
            "位元組都留下紀錄，但說不出每一通各對應哪一個工具事件")
    elif enc_ok:
        tier, kind = TIER_B, None
        reasons.append("圍牆成立、**掛鉤沒燒**（canary_fired="
                       f"{framework_hook.get('canary_fired')!r}）")
    elif hook_ok:
        tier = TIER_B_PRIME
        kind = ("in_process_model" if in_process_model is True
                else "channel_not_enclosed")
        reasons.append(
            "掛鉤燒了但**圍牆不成立**"
            f"（enclosure.applied={enclosure.get('applied')!r}）⇒ "
            + ("模型在行程內，通道不在網路上"
               if kind == "in_process_model"
               else "模型通道在網路上，但不保證每一通都經過 Vacant"))
    elif in_process_model is True:
        tier, kind = TIER_B_PRIME, "in_process_model"
        reasons.append("模型在行程內；圍牆與掛鉤都不成立 ⇒ 只剩工具層那一半")
    else:
        tier, kind = TIER_C, None
        reasons.append(
            "圍牆不成立而且掛鉤沒燒 ⇒ **未受控**。"
            f"（enclosure.applied={enclosure.get('applied')!r}、"
            f"canary_fired={framework_hook.get('canary_fired')!r}）")
    if enclosure.get("applied") is None:
        reasons.append("⚠ 圍牆那一欄是「沒量到」不是「量到 false」")
    if framework_hook.get("canary_fired") is None:
        reasons.append("⚠ 掛鉤那一欄是「沒量到」不是「量到 false」")
    if reconciled.get("unexplained") is None:
        reasons.append("⚠ 對帳那一欄是「沒量到」不是「量到 0」")
    return {"tier": tier, "attested": tier == TIER_A,
            "b_prime_kind": kind, "sentence": TIER_SENTENCE[tier],
            "reasons": reasons}


# ── 5. 組裝 ────────────────────────────────────────────────────────────

def attest(*, agent: str | None = None, run_id: str | None = None,
           enclosure: dict | None = None,
           policy_path: str | os.PathLike | None = None,
           door_sock: str | None = None,
           hook_log: str | os.PathLike | None = None,
           install_attempted: bool | None = None,
           relay_index: str | os.PathLike | None = None,
           relay_since: int = 0,
           in_process_model: bool | None = None,
           host_pid: int | None = None) -> dict:
    """把四個欄位組成一塊，**收據直接放這一塊**。

    `enclosure=` 給了就用給的那一份（`--probe` 在圍牆裡量好的）；
    沒給就當場量（`gateshim` 那條路，探針與 agent 同一個行程樹）。
    """
    enc = enclosure if enclosure is not None else probe_enclosure(
        policy_path=policy_path, door_sock=door_sock)
    if host_pid is not None:
        enc.setdefault("probe", {})["host_ns_of_pid"] = {
            "pid": host_pid, "ns_id": host_ns_of_pid(host_pid),
            "note": "主機側直接讀 kernel，不經過圍牆裡任何人的手（誠實邊界 2）"}
    hook = probe_framework_hook(agent=agent, hook_log=hook_log, run_id=run_id,
                                install_attempted=install_attempted)
    rec = reconcile(relay_calls=read_relay_calls(relay_index,
                                                 since=relay_since),
                    hook_events=read_hook_events(hook_log, run_id=run_id),
                    run_id=run_id)
    g = grade(enc, hook, rec, in_process_model=in_process_model)
    out = {
        "schema": "vacant-attest/1",
        "run_id": run_id, "agent": agent,
        "enclosure": enc, "framework_hook": hook, "reconciled": rec,
        "tier": g["tier"], "attested": g["attested"],
        "b_prime_kind": g["b_prime_kind"],
        "tier_sentence": g["sentence"], "tier_reasons": g["reasons"],
        "in_process_model": in_process_model,
        "assembled_at": time.time(),
    }
    # 出門前再驗一次三態——欄位是給別人讀的，型別壞掉比少一個欄位嚴重
    assert_three_state(out["enclosure"], ("applied",), label="enclosure.")
    assert_three_state(out["framework_hook"], ("canary_fired",),
                       label="framework_hook.")
    assert_count_three_state(out["reconciled"],
                             ("relay_calls", "hook_events", "unexplained"),
                             label="reconciled.")
    return out


#: 級別 → 退出碼。**`gateshim` 從這裡讀，不要在兩個地方各寫一份。**
#: A 級回 `None` ＝ 「不覆蓋既有退出碼」（0／20／21／22／23 原樣）。
TIER_EXIT = {TIER_A: None, TIER_B: 24, TIER_B_PRIME: 25, TIER_C: 26}


# ── CLI ────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="vacant attest",
        description="收據的對帳欄位與 fail-closed 分級（裁決 §二 P0）")
    ap.add_argument("--probe", action="store_true",
                    help="**跑在圍牆裡面**：只量 enclosure 那一塊，印 JSON")
    ap.add_argument("--assemble", action="store_true",
                    help="**跑在主機上**：把探針結果 ＋ journal ＋ 掛鉤日誌組成收據欄位")
    ap.add_argument("--probe-json", help="--assemble 用：--probe 產出的檔")
    ap.add_argument("--policy", help="圍牆政策檔（預設 /run/vacant/policy.json）")
    ap.add_argument("--door-sock", help="門的 unix socket（預設 /run/vacant/relay.sock）")
    ap.add_argument("--hook-log", help="掛鉤日誌 JSONL")
    ap.add_argument("--relay-index", help="門／proxy 的 wire/index.jsonl")
    ap.add_argument("--relay-since", type=int, default=0,
                    help="這一跑開始前那份 journal 已經有幾行")
    ap.add_argument("--run-id")
    ap.add_argument("--agent")
    ap.add_argument("--install-attempted", choices=("yes", "no", "unknown"),
                    default="unknown",
                    help="我們有沒有**試著**裝掛鉤。⚠ 這只影響「沒量到 vs 量到 false」"
                         "的分辨，**不影響 canary_fired 本身**（那一欄只讀日誌）")
    ap.add_argument("--in-process-model", choices=("yes", "no", "unknown"),
                    default="unknown")
    ap.add_argument("--host-ns-of-pid", type=int, default=None,
                    help="主機側交叉驗證：讀 /proc/<pid>/ns/net")
    ap.add_argument("--out", help="寫到這個檔（同時也印到 stdout）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    tri = {"yes": True, "no": False, "unknown": None}
    if a.probe and a.assemble:
        ap.error("--probe 與 --assemble 是兩段不同的量測，一次只能做一段")
    if a.probe:
        doc: dict = probe_enclosure(policy_path=a.policy,
                                    door_sock=a.door_sock)
    elif a.assemble:
        enc = None
        if a.probe_json:
            enc = json.loads(pathlib.Path(a.probe_json).read_text("utf-8"))
        doc = attest(agent=a.agent, run_id=a.run_id, enclosure=enc,
                     policy_path=a.policy, door_sock=a.door_sock,
                     hook_log=a.hook_log, relay_index=a.relay_index,
                     relay_since=a.relay_since,
                     install_attempted=tri[a.install_attempted],
                     in_process_model=tri[a.in_process_model],
                     host_pid=a.host_ns_of_pid)
    else:
        ap.error("要 --probe（圍牆裡）或 --assemble（主機上）")
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    if a.out:
        pathlib.Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    if a.probe:
        return 0
    return 0 if doc.get("tier") == TIER_A else (TIER_EXIT[doc["tier"]] or 0)


def selftest() -> int:      # pragma: no cover - 由 tests/ 逐格驗，這裡只是自檢入口
    """最小自檢：四級各一格 ＋ 三態不可互換。詳細的負控制在 `tests/`。"""
    bad: list[str] = []

    def ck(label: str, cond: bool, extra: str = "") -> None:
        if not cond:
            bad.append(f"{label}　{extra}")

    enc_t = {"applied": True, "ns_id": "net:[1]", "policy_sha256": "x"}
    enc_f = {"applied": False, "ns_id": None, "policy_sha256": None}
    enc_n = {"applied": None, "ns_id": None, "policy_sha256": None}
    hk_t = {"canary_fired": True}
    hk_f = {"canary_fired": False}
    hk_n = {"canary_fired": None}
    r0 = {"unexplained": 0}
    r1 = {"unexplained": 1}
    rn = {"unexplained": None}
    ck("A", grade(enc_t, hk_t, r0)["tier"] == TIER_A)
    ck("B_no_hook", grade(enc_t, hk_n, rn)["tier"] == TIER_B)
    ck("B_recon_fail", grade(enc_t, hk_t, r1)["tier"] == TIER_B)
    ck("Bprime", grade(enc_f, hk_t, r0)["tier"] == TIER_B_PRIME)
    ck("C", grade(enc_f, hk_f, rn)["tier"] == TIER_C)
    ck("unmeasured_is_not_A", grade(enc_n, hk_n, rn)["tier"] == TIER_C)
    ck("unexplained_None_is_not_zero",
       grade(enc_t, hk_t, rn)["tier"] == TIER_B)
    try:
        assert_three_state({"applied": 0}, ("applied",))
        ck("zero_is_not_three_state", False, "0 混進布林三態竟然過了")
    except ValueError:
        pass
    try:
        assert_count_three_state({"relay_calls": False}, ("relay_calls",))
        ck("bool_is_not_count", False, "False 混進數字三態竟然過了")
    except ValueError:
        pass
    for b in bad:
        print("✗ " + b, file=sys.stderr)
    print(f"attest selftest: {'PASS' if not bad else f'FAIL({len(bad)})'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
