"""twin/to_events — `vacant run` 的 run 目錄 → 人類動物園電視吃的 world event。

## 這支在架構裡承重什麼：**這就是「接好 vacant world」那一條線**

電視（`vacant_hm/world3/index.html`）早就寫好了活模式：`?live=<串流網址>&poll=2000`，
它每隔幾秒抓一次、依 `ts|type|task_id|arm|reviewer` 去重、把事件組成一筆可播的紀錄。
契約寫在 `vacant_hm/world3/docs/LIVE_INTERFACE.md`。

⇒ 凍結重放與真跑 agent 吐同一種事件，換資料源不用改電視。

## v2（2026-09-19）：忠實度稽核之後的重寫

人類的要求：「現在的數位分身的邏輯跟我們真實的不太一樣，就改好來，改成最終版
VACANT 的邏輯忠實呈現。」對照表與逐條理由在
`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md`。v1 這一支自己犯的三條：

1. **`accepted` 被 `bool()` 壓成兩值。** `--allow-no-suite` 的格子 `accepted`
   是 `None`（＝**沒量**），`bool(None)` ⇒ `false`（＝**量了，沒過**）。
   這與電視那條 `meets_demand: !!v.meets_demand`（把 null 收斂成 false）
   是**同一種錯**，而且是在我們自己這一端。「沒量」與「量到沒過」不可以同形。
2. **`blocked_by` 寫死 `"gate"`。** 真正的 `stop_reason` 有
   `visible_fail`／`attempts_exhausted`／`no_suite`／`ungated` 四種形狀，
   壓成一個字等於把四件事講成一件事。
3. **整個重試迴圈被壓成一格。** V1 的機制本體（**閘門 → 回饋 → 再 spawn 一次**，
   R530／R532 量到增益的那個東西）在 v1 的事件裡完全看不見：一次 `draft_done`、
   一次 `gate_ran`，`attempts_used` 連發都沒發。
   **展件在演 Vacant，卻把 Vacant 唯一被量到有用的那一段刪掉了。**

## 對照表（左邊是 `vacant run` 落盤的東西，右邊是 LIVE_INTERFACE.md 的 type）

| 事件 | 從哪來 | 備註 |
|---|---|---|
| `task_opened` | 工作區的 `TASK.md` | `prompt_sha256` ＝ 題面的 sha256；另帶 `evidence` |
| `routed` | 名冊 | `basis` 固定 `"random"`——**這一批沒有信譽路由**，不准寫成有 |
| `draft_done` | `attempts[i]` | **每一次嘗試各發一筆**，`calls_used` ＝ 那一次的 `requests_seen` |
| `gate_ran` | `attempts[i].visible` | **每一次嘗試各發一筆**，各自的閘門結果 |
| `revised` | `attempts[i+1]` 存在時 | `reviser` ＝ **同一個 worker**（不是別人），見誠實邊界 4 |
| `verdict` | 鏈上的 `ws_verdict` | **讀簽章覆蓋的那一份**，不讀 run 摘要 |
| `receipt` | 鏈頭 | `verify_url` 指向離線收據頁 |
| `counters` | 整批累計 | 真實累計值，不是估計 |

**沒發生的步驟不發事件**（LIVE_INTERFACE.md 的硬性誠實規則）：`vacant run`
**沒有同儕評審、沒有抽樣稽核、沒有路由層**，所以 `review_vote`／`audited`
**一個都不發**，`counters` 也**不發 `audited`**——「這條路上沒有這一層」
與「抽了 0 次」不是同一件事，發一個 `audited: 0` 就是把沒有的層畫成有。

## v2.1（2026-09-19 傍晚）：反事實那一臂**真的跑了**

在此之前展件只有 ON 臂，`liveAssemble` 寫死 `OFF: null`，而電視的監視器照樣印
「同題關掉這層：**也擋下**」——替一個沒發生的反事實作證（對照表 A4，
「展場的主視覺就是這個對照，這條錯得最貴」）。現在每一格都有一串 `arm: "OFF"`
的事件，來自 `vacant run --vacant 0` 的真跑。

那一臂發 `draft_done` ＋ `verdict(accepted: null, stop_reason: "ungated")`，
**不發 `gate_ran`**（沒有閘門）、**不發 `receipt`**（不簽收據），
另外發一筆契約外的 `postaudit`＝**事後**用同一把尺量 OFF 那份交付的結果，
自己帶著 `when="after_the_run"`／`is_verdict=false`／`signed=false`。
逐條理由見 `off_events` 的 docstring，可執行判準在 `validate`。

⚠ **但不發事件擋不住電視自己編。** 電視在沒有 `review_vote` 的時候仍然會進
s07 演「三人同儕評審：0/0 判可」、在沒有 `audited` 的時候仍然印「沒抽中」。
那六條要電視端改，提案（未套用）在 `ops/exhibit/twin/world3_patch/`。
**生產端能做的到此為止：我們不發假事件，也不能替電視說話。**

## 誠實邊界

1. `basis` 只有在路由真的由信譽層決定時才准填 `"reputation"`。`vacant run` 沒有
   路由層——一格一個 agent，誰做是人指定的。所以這支**寫死 `"random"`**，
   而且不提供參數改它：一個可以用旗標改成 `"reputation"` 的欄位遲早會被改。
2. `meets_demand` 需要隱藏測資才答得出來，而隱藏測資不准進展件（V/GT 紅線）。
   所以本支**不發** `meets_demand=true`——`verdict` 只帶 `accepted`
   （可見驗收過了沒），`meets_demand` 留成 `null`，電視顯示「—」。
   把 `accepted` 寫成 `meets_demand` 就是把「通過驗收」講成「符合需求」。
3. `accepted` 是**三值**：`true`（量了，過）／`false`（量了，沒過）／
   `null`（沒量，＝`--allow-no-suite`）。本支不做 `bool()`。
4. **`revised` 的 `reviser` 是同一個 worker，不是另一個人。** Vacant 的重改是
   「同一個 agent 帶著自己的失敗原文再跑一次」，不是「評審推翻之後換人重寫」。
   `transition` 逐字寫出是哪一條臂（`revise` 保留工作區＋餵失敗原文；
   `resample` 重置回起點＋不餵原文）。把它演成換人重寫就是演了別的系統。
5. 事件流本身**沒有簽章**（LIVE_INTERFACE.md §四 已經記了這條）。
   可驗的那一份是收據頁，不是這條串流。電視是展示端不是證據端。
6. `evidence` 是**推**出來的（`pack.evidence_level`：`requests_seen == 0`
   一律 L-none，宣告蓋不過去），不是這支宣告的。發它是因為電視的誠實列在活模式
   寫死「判決與數字＝正在發生的真實 agent」——那句話對 L-none 的格子是假的，
   電視要有資料才改得對。

用法：
    # 一次性產生整批事件（離線重放用）
    python3 ops/exhibit/twin/to_events.py --runs runs/twin_fixture_20260919 \\
        --out runs/twin_fixture_20260919/events.jsonl

    # 電視端：world3/index.html?live=<events.jsonl 的網址>&poll=2000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import pack as packlib  # noqa: E402

ARM = packlib.ARM

#: 每個事件都必須有的欄位（LIVE_INTERFACE.md §一）。
REQUIRED = ("type", "ts", "task_id")

#: 本支發得出來的 type。沒列在這裡的一律不發（誠實規則：沒發生就不發）。
#: `postaudit` 是 2026-09-19 加的，**不是契約裡的步驟**——見 `OFF_ARM` 那一節。
EMITTED = ("task_opened", "routed", "draft_done", "gate_ran", "revised",
           "verdict", "receipt", "counters", "postaudit")

#: 事件的 `arm` 欄位。契約（LIVE_INTERFACE.md §一）本來只把它用在去重鍵上，
#: 沒有規定值。這裡把它定成兩個字串，因為從 2026-09-19 起**一格有兩串事件**。
ARM_ON, ARM_OFF = "ON", "OFF"

#: **這條路上不存在的層**。發了就是把沒有的東西畫出來。
NEVER = ("review_vote", "audited")

#: `stop_reason` → `blocked_by`（契約只有 `gate`／`review`／null 三值）。
#: `review` 永遠不會出現：這條路上沒有評審層。
BLOCKED_BY = {
    "visible_fail": "gate",          # 量了，沒過
    "attempts_exhausted": "gate",    # 量了 N 次都沒過
    "no_suite": "gate",              # 沒有驗收套件 ⇒ fail-closed，閘門擋的
    "visible_pass": None,            # 收下了
    "ungated": None,                 # **沒量**：不是被擋，是沒有量具
}

#: 回饋**走哪一條管道**。展場上這一句不能省：`feedback_in_prompt_bytes = 0`
#: 在 `file` 管道底下是**每一次都 0**，而那不代表「沒有回饋」。
FEEDBACK_NOTE = {
    "file": "回饋寫進工作區的 VACANT_FEEDBACK.md。**它有沒有去讀是另一回事**"
            "——R535 量過檔案這條管道在 wire 上零命中。",
    "prompt": "回饋接在下一次 spawn 的 prompt 尾端（位元組數在 feedback_bytes）。",
    "both": "回饋同時寫進工作區的檔案、並接在下一次 spawn 的 prompt 尾端。",
}

#: 重試臂 → 一句話說清楚「下一次是在什麼條件下跑的」。
TRANSITION = {
    "revise": "gate_fail→revise：保留工作區，把可見驗收的失敗原文寫進 "
              "VACANT_FEEDBACK.md，同一個 agent 再跑一次",
    "resample": "gate_fail→resample：工作區重置回起點（含 .git），"
                "不給失敗原文，同一個 agent 重跑一次",
    "none": "沒有重試臂（--retry none）",
}


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _signed_accepted(cell: dict):
    """裁決讀**簽章覆蓋的那一份**，不讀 run 摘要。三值，不做 `bool()`。"""
    accepted = None
    for line in cell["chain"]:
        d = json.loads(line)
        if d["type"] == "ws_verdict":
            payload = d["payload"]
            # `accepted_is_null` ＝ `--allow-no-suite` 那一格：鏈上的 `accepted`
            # 欄位型別是 bool，所以「沒量」另外用一個旗標簽進去（launcher.py:677）。
            accepted = None if payload.get("accepted_is_null") \
                else payload.get("accepted")
    return accepted


def off_events(cell: dict, tid: str, ev) -> None:
    """反事實那一臂：**同一題、關掉這一層**。沒跑過就一個事件都不發。

    ## 為什麼這一段存在

    電視的監視器印著「同題關掉這層：**也擋下**」，而在 2026-09-19 之前
    那一臂**一次都沒跑過**（`liveAssemble` 寫死 `OFF: null`）——
    替一個沒發生的反事實作證。**現在它是真的跑出來的**，所以那句話
    第一次有東西可以指。

    ## 這一臂發什麼、不發什麼（每一條都是誠實規則，不是美觀選擇）

    | 發 | 不發 | 理由 |
    |---|---|---|
    | `draft_done` | — | 它真的做了一份東西，`calls_used` 是真的通數 |
    | — | **`gate_ran`** | **這一臂沒有閘門**。發一筆 `passed:false` 就是把「沒有這一層」演成「這一層也判了」 |
    | `verdict`（`accepted: null`） | — | 三值裡的 null ＝**沒量**。`stop_reason` 恆為 `ungated` |
    | — | **`receipt`** | **這一臂不簽收據**。觀眾在這一邊沒有任何東西可以自己重驗——那正是展件要讓人看見的那一格差別 |
    | `postaudit` | — | 事後用同一把尺量的，自己帶著「事後、非裁決、未簽章」三個旗標 |

    ⚠ `postaudit` **不在 LIVE_INTERFACE.md 的契約裡**。電視不認得它 ⇒ 會忽略它
      （`liveAssemble` 只 `get()` 它認得的 type），所以加它不會讓現在的電視變壞；
      但電視要印出「關掉這層會怎樣」就**只能**讀它，而它的名字與旗標讓
      「事後稽核」與「當場裁決」在資料上永遠分得開。
    """
    off = cell.get("off")
    if not off or not off.get("ran"):
        return
    if off.get("infra_void"):
        # 鐵律 3：跑掛的那一臂**不發事件**。「沒量到」不可以長成一個數字。
        ev("verdict", arm=ARM_OFF, accepted=None, meets_demand=None,
           blocked_by=None, stop_reason="infra_void",
           infra_void=str(off.get("infra_void")),
           note="這一臂的基建壞了 ⇒ 沒有量到任何東西。不是「沒過」，是「沒跑成」。",
           attempts_used=off.get("attempts_used"), retry="none")
        return
    ev("draft_done", arm=ARM_OFF, worker=cell["resident"],
       calls_used=int(off.get("requests_seen") or 0),
       attempt=1, of=1, feedback_bytes=0,
       timed_out=bool(off.get("agent_timed_out")),
       timed_out_note=("這一臂也是跑到牆鐘上限被砍掉的：事後稽核量到的是"
                       "它寫到一半的工作區。"
                       if off.get("agent_timed_out") else ""),
       note="沒有 Vacant 的那一臂：一次 spawn、沒有閘門、沒有回饋、沒有第二次。")
    # ⚠ **不發 `gate_ran`**：這一臂沒有閘門。
    ev("verdict", arm=ARM_OFF,
       accepted=None,          # 沒量（不是量到 false）
       meets_demand=None,
       blocked_by=None,        # 沒有東西擋它
       stop_reason=off.get("stop_reason") or "ungated",
       accepted_note=off.get("accepted_note", ""),
       has_receipt=bool(off.get("has_receipt")),
       has_receipt_note=off.get("has_receipt_note", ""),
       attempts_used=off.get("attempts_used"), retry="none")
    pa = off.get("postaudit")
    if pa:
        ev("postaudit", arm=ARM_OFF,
           # ⚠ 三個旗標一起走，缺一個就會被讀成裁決。
           when=pa.get("when"), is_verdict=False, signed=False,
           all_pass=bool(pa.get("all_pass")),
           passed=pa.get("passed"), n_tests=pa.get("total"),
           failed_case=next((c["case"] for c in (pa.get("cases") or [])
                             if not c["ok"]), None),
           ruler=pa.get("ruler"), note=pa.get("note"))


def events_for_cell(cell: dict, *, verify_url: str, ts_ms: int) -> list[dict]:
    """一格 → 一串事件。`cell` 是 `pack.pack_cell()` 的輸出。

    `task_id` 用 `cell_id`：電視的去重鍵是 `ts|type|task_id|arm|reviewer`，
    同一題在不同居民手上是**不同的一格**，共用 task_id 會被去重吃掉一格。

    ⚠ **順序是 ON 全部、然後 OFF 全部**，不是交錯。理由是現在那台電視
      （未套 patch）的 `liveAssemble` 用 `evs.find(e => e.type === t)` 取
      **第一個**符合的事件 ⇒ ON 先發 ⇒ 它組出來的仍然是 ON 臂那一筆，
      與加 OFF 之前逐位元同義。**加資料不准讓現況變壞**；
      要讀得到 OFF 是電視端那一條 patch 的事（忠實度對照表 P10）。
    """
    tid = cell["cell_id"]
    out: list[dict] = []
    step = 0

    def ev(kind: str, **kw) -> None:
        nonlocal step
        step += 1
        out.append({"type": kind, "ts": iso(ts_ms + step * 1000),
                    "task_id": tid, **kw})

    prompt = ""
    for f in (cell.get("delivery") or {}).get("files", []):
        if f["path"] == "TASK.md" and f.get("text"):
            prompt = f["text"]
    ev("task_opened", prompt=prompt,
       prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
       # 證據等級是推出來的，不是宣告的（誠實邊界 6）。電視的誠實列要用它。
       evidence=cell["evidence"],
       evidence_note=packlib.EVIDENCE_TEXT.get(cell["evidence"], ""),
       # 這一格用的是哪一份題面：`held`＝介面被扣住，`pc`＝介面寫明。
       stratum="pc" if cell.get("explicit") else "held")

    # basis 寫死 random：vacant run 沒有路由層，誰做這一格是人指定的（誠實邊界 1）。
    ev("routed", worker=cell["resident"], basis="random",
       basis_note="`vacant run` 沒有路由層：誰做這一格是人指定的，不是信譽決定的")

    # ── 每一次嘗試各發一筆 draft_done ＋ gate_ran ───────────────────
    # 這就是 V1 的機制本體（閘門 → 回饋 → 再 spawn 一次）。壓成一格＝把
    # Vacant 唯一被量到有用的那一段刪掉。
    attempts = cell.get("attempts") or []
    if not attempts:
        # 舊資料包（沒有 attempts）：退回單次形狀，但不假裝知道有幾次。
        attempts = [{"attempt": 1, "requests_seen": cell["requests_seen"],
                     "visible": cell["visible"], "stop_reason": cell["stop_reason"]}]
    n_total = len(attempts)
    retry_arm = cell.get("retry") or "none"
    for i, a in enumerate(attempts):
        n = int(a.get("attempt") or (i + 1))
        ev("draft_done", arm=ARM_ON, worker=cell["resident"],
           calls_used=int(a.get("requests_seen") or 0),
           attempt=n, of=n_total,
           # 回饋真的進了幾個位元組。第 1 次恆為 0 ⇒「與沒有 Vacant 時逐位元
           # 相同」這件事在資料上自己說得出來。
           feedback_bytes=a.get("feedback_in_prompt_bytes"),
           # ⚠ **沒有這個欄位，上面那個 0 會說謊。**
           #   `--feedback-into file`（預設）＝回饋寫進工作區的
           #   `VACANT_FEEDBACK.md`，**不進 prompt** ⇒ 每一次嘗試的
           #   `feedback_in_prompt_bytes` 都是 0。畫面上只看到一串 0，
           #   會被讀成「根本沒給它回饋」——而回饋其實給了，只是走檔案。
           #   兩件事在展場上差很多：一個是機制沒動，一個是機制動了而
           #   agent 沒去讀（R535 量到的正是後者：檔案投遞在 wire 上零命中）。
           feedback_delivery=a.get("feedback_delivery"),
           feedback_note=FEEDBACK_NOTE.get(a.get("feedback_delivery") or "", ""),
           # ⚠ **被牆鐘上限砍掉**與**自己跑完但沒過**是兩個故事，而兩者的
           #   `stop_reason` 都是 `visible_fail`（工作區照樣凍結、照樣送驗收）。
           #   不帶這一欄，電視會把「我們沒等它」演成「它做不出來」。
           timed_out=bool(a.get("agent_timed_out")),
           timed_out_note=("這一次是跑到牆鐘上限被砍掉的：交出去驗收的是它當下"
                           "寫到一半的工作區。「沒過」有一部分是我們沒等它。"
                           if a.get("agent_timed_out") else ""),
           agent_wall_s=a.get("agent_wall_s"))
        vis = a.get("visible")
        if vis is None:
            # 沒有閘門結果（沒有驗收套件／基建中止）⇒ **不發 gate_ran**。
            continue
        failed = next((c["case"] for c in (vis.get("cases") or [])
                       if not c["ok"]), None)
        ev("gate_ran", arm=ARM_ON, passed=bool(vis.get("all_pass")),
           n_tests=vis.get("total"), failed_case=failed,
           attempt=n, of=n_total)
        if i + 1 < n_total:
            # 下一次嘗試存在 ⇒ 這一次沒過而且還有額度。
            # ⚠ reviser ＝ **同一個 worker**（誠實邊界 4）。
            # ⚠ **`arm` 與 `retry_arm` 是兩個不同的東西，2026-09-19 才分開。**
            #   v2 把重試臂（`revise`／`resample`）寫在一個叫 `arm` 的欄位裡，
            #   而電視的去重鍵是 `ts|type|task_id|arm|reviewer`——同一個欄位
            #   同時要當「ON 還是 OFF」與「revise 還是 resample」用。
            #   加了 OFF 臂之後這就會壞：patch 過的電視按 `arm` 分組時，
            #   `revised` 會掉進一個叫 `"revise"` 的第三組，那一格的重改拍
            #   就從 ON 那一串裡消失。⇒ 重試臂改名 `retry_arm`，`arm` 專職分臂。
            ev("revised", arm=ARM_ON, reviser=cell["resident"],
               transition=TRANSITION.get(retry_arm, retry_arm),
               retry_arm=retry_arm, attempt=n + 1, of=n_total)

    accepted = _signed_accepted(cell)
    stop = cell.get("stop_reason") or ""
    ev("verdict", arm=ARM_ON,
       # 三值，不做 bool()：null ＝ 沒量（誠實邊界 3）
       accepted=accepted,
       # meets_demand 要隱藏測資才答得出來，而隱藏測資不進展件 ⇒ 留 null（誠實邊界 2）
       meets_demand=None,
       blocked_by=BLOCKED_BY.get(stop, "gate" if accepted is False else None),
       stop_reason=stop,
       attempts_used=cell.get("attempts_used"),
       retry=retry_arm)

    head = ""
    if cell["chain"]:
        from vacant.logbook import LogEntry
        head = LogEntry.from_json(json.loads(cell["chain"][-1])).hash()
    ev("receipt", arm=ARM_ON, sha256=head, chain_head=head, verify_url=verify_url,
       # ⚠ 契約的 `sha256` 是**收據**的，電視 v1 卻把它塞進一個叫
       #   `prompt_sha256` 的欄位（world3_patch 的第 2 條）。這兩個
       #   hash 各自帶一份，patch 過的電視才有東西可以分開顯示。
       prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
       verdict_sha256=cell.get("verdict_sha256"),
       ws_end_sha256=cell.get("ws_end_sha256"))

    # ── 反事實那一臂，**接在 ON 全部發完之後** ───────────────────────
    #  順序的理由寫在本函式的 docstring：未套 patch 的電視取「第一個」，
    #  ON 先發 ⇒ 它組出來的還是 ON 那一筆，加資料沒有讓現況變壞。
    off_events(cell, tid, ev)
    return out


def build(pack: dict, *, verify_url: str, t0_ms: int) -> list[dict]:
    evs: list[dict] = []
    ts = t0_ms
    for cell in pack["cells"]:
        block = events_for_cell(cell, verify_url=verify_url, ts_ms=ts)
        evs.extend(block)
        ts += (len(block) + 2) * 1000
    # counters 是真實累計值，不是估計（LIVE_INTERFACE.md 的硬性規則）。
    # `on_leaked`／`off_leaked` 要隱藏測資才答得出來 ⇒ 不發那兩欄，電視顯示「—」。
    # `audited` **也不發**：這條路上沒有抽樣稽核層，發 0 就是把沒有的層畫成
    # 「有這一層，只是這次沒抽中」。沒有與抽了 0 次不是同一件事。
    levels: dict[str, int] = {}
    for c in pack["cells"]:
        levels[c["evidence"]] = levels.get(c["evidence"], 0) + 1
    ctr = {
        "type": "counters", "ts": iso(ts), "task_id": "-",
        "blocked": pack["refused"], "total": len(pack["cells"]),
        "delivered": pack["delivered"],
        "evidence_counts": dict(sorted(levels.items())),
    }
    # 反事實那一臂的累計。**欄名刻意又臭又長**：`off_postaudit_not_all_pass`
    # 讀起來就是「事後用可見驗收量，沒有全過的格數」，沒有辦法被誤讀成
    # `off_leaked`（那要隱藏測資才答得出來，而隱藏測資不進展件）。
    offs = [c["off"] for c in pack["cells"] if c.get("off")
            and c["off"].get("ran") and not c["off"].get("infra_void")]
    if offs:
        audited = [o for o in offs if o.get("postaudit")]
        ctr.update({
            "off_ran": len(offs),
            "off_with_receipt": sum(1 for o in offs if o.get("has_receipt")),
            "off_postaudited": len(audited),
            "off_postaudit_not_all_pass": sum(
                1 for o in audited if not o["postaudit"].get("all_pass")),
            "off_counters_note":
                "OFF 臂沒有裁決可以計數（它不驗收）。這幾欄是**事後**用同一份"
                "可見驗收量出來的，不是那一跑當場的判定。",
        })
    evs.append(ctr)
    return evs


def validate(evs: list[dict]) -> list[str]:
    """契約自檢：每個事件都要有必要欄位、type 要在白名單、ts 要單調不減。"""
    bad = []
    last = ""
    for i, e in enumerate(evs):
        for k in REQUIRED:
            if k not in e:
                bad.append(f"第 {i + 1} 個事件缺欄位 {k}")
        if e.get("type") in NEVER:
            bad.append(f"第 {i + 1} 個事件是這條路上不存在的層：{e.get('type')!r}")
        elif e.get("type") not in EMITTED:
            bad.append(f"第 {i + 1} 個事件的 type 不在白名單：{e.get('type')!r}")
        if e.get("ts", "") < last:
            bad.append(f"第 {i + 1} 個事件的 ts 比前一個早")
        last = e.get("ts", last)
        # 「沒量」不可以在資料上長成「量到沒過」（誠實邊界 3）。
        if e.get("type") == "verdict" and e.get("stop_reason") == "ungated" \
                and e.get("accepted") is not None:
            bad.append(f"第 {i + 1} 個事件：`ungated`（沒量）卻給了 accepted 布林值")
        if e.get("type") == "verdict" and e.get("meets_demand") is not None:
            bad.append(f"第 {i + 1} 個事件：meets_demand 只能是 null"
                       "（要隱藏測資才答得出來，而隱藏測資不進展件）")
        if e.get("type") == "routed" and e.get("basis") != "random":
            bad.append(f"第 {i + 1} 個事件：basis 不是 random"
                       "（`vacant run` 沒有路由層）")
        if e.get("type") == "revised" and e.get("reviser") is None:
            bad.append(f"第 {i + 1} 個事件：revised 沒有 reviser")
        # ── 反事實那一臂的三條硬規則 ────────────────────────────────
        if e.get("arm") == ARM_OFF:
            if e.get("type") == "gate_ran":
                bad.append(f"第 {i + 1} 個事件：OFF 臂發了 gate_ran——"
                           "**那一臂沒有閘門**，發了就是把「沒有這一層」"
                           "演成「這一層也判了」")
            if e.get("type") == "receipt":
                bad.append(f"第 {i + 1} 個事件：OFF 臂發了 receipt——"
                           "**那一臂不簽收據**，觀眾在這一邊沒有東西可以自己重驗")
            if e.get("type") == "verdict" and e.get("accepted") is not None:
                bad.append(f"第 {i + 1} 個事件：OFF 臂的 accepted 不是 null——"
                           "那一臂不驗收也不拒交，沒有裁決可言")
        # 事後稽核不准長得像裁決：三個旗標缺一不可。
        if e.get("type") == "postaudit":
            if e.get("is_verdict") is not False or e.get("signed") is not False:
                bad.append(f"第 {i + 1} 個事件：postaudit 必須自己說 "
                           "`is_verdict=false`＋`signed=false`，"
                           "否則它與當場的裁決在資料上分不開")
            if e.get("when") != "after_the_run":
                bad.append(f"第 {i + 1} 個事件：postaudit 沒說它是事後量的")
    # 電視的去重鍵：ts|type|task_id|arm|reviewer。撞鍵 ⇒ 那一格會被靜靜吃掉。
    keys = ["%s|%s|%s|%s|%s" % (e.get("ts"), e.get("type"), e.get("task_id"),
                                e.get("arm", ""), e.get("reviewer", "")) for e in evs]
    if len(set(keys)) != len(keys):
        bad.append("有事件撞到電視的去重鍵，會被靜靜吃掉一格")
    # 每一格都要走到 verdict，否則電視的 liveAssemble 會一直等
    # （而且會**卡住整個佇列**：它只看 pending[0] 的 task_id）。
    opened = {e["task_id"] for e in evs if e["type"] == "task_opened"}
    settled = {e["task_id"] for e in evs if e["type"] == "verdict"}
    for t in sorted(opened - settled):
        bad.append(f"{t} 開了但沒有 verdict：電視會一直等這一格（整個佇列卡住）")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="把 twin run 目錄轉成人類動物園電視吃的 world event JSONL")
    ap.add_argument("--runs", default=None, help="run_twin.py 的 --out 根目錄")
    ap.add_argument("--pack", default=None, help="或直接給 twin_pack.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--verify-url", default="twin_viewer.html",
                    help="觀眾自己重驗收據的那一頁（LIVE_INTERFACE.md §四的缺口）")
    ap.add_argument("--t0-ms", type=int, default=1_789_000_000_000)
    a = ap.parse_args(argv)

    if a.pack:
        pack = json.loads(pathlib.Path(a.pack).read_text(encoding="utf-8"))
    elif a.runs:
        pack = packlib.build(pathlib.Path(a.runs).resolve())
    else:
        raise SystemExit("--runs 或 --pack 要給一個")

    evs = build(pack, verify_url=a.verify_url, t0_ms=a.t0_ms)
    bad = validate(evs)
    for b in bad:
        print("[BROKEN] " + b)
    if bad:
        return 1
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(e, ensure_ascii=False, sort_keys=True)
                             for e in evs) + "\n", encoding="utf-8")
    kinds: dict[str, int] = {}
    for e in evs:
        kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    print("寫出 %s：%d 個事件 %s" % (out, len(evs), kinds))
    print("  沒發的 type（這條路上沒有這一層）：review_vote／audited")
    print("  ⚠ 不發事件擋不住電視自己編——電視端還要 world3_patch 的六條")
    return 0


if __name__ == "__main__":
    sys.exit(main())
