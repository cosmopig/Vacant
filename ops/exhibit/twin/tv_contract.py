"""twin/tv_contract — 電視（人類動物園 `world3`）吃的 world event 契約：常數＋可執行自檢。

## 這支在架構裡承重什麼

展場只剩一條路（2026-09-24 人類裁決「刪事後推導，留錄影重播」）：

```
 vacant run --events ──lifecycle.jsonl──▶ live_events.Folder ──world event──▶ 電視 ?live=
   （現場真跑，或錄下來的那一份）           唯一一支轉換器          這一支定的契約
```

**這一支不產生任何事件。** 它只定「電視事件長什麼樣、哪些話不准說」，
產生事件的只有 `live_events.Folder`（現場真跑與重播錄影走同一支）。
在此之前這些常數住在 `to_events.py`（從 run 目錄事後推事件的那一條），
那一條已經刪掉；常數與自檢搬到這裡，讓轉換器不必 import 一條已經不存在的路。

電視那一側的契約文件是 `vacant_hm/world3/docs/LIVE_INTERFACE.md`（另一個 repo，
A 線維護）。**兩邊的欄位必須一字不差**；本支是生產端的那一份可執行版本。

## 契約（生產端的承諾）

每一筆事件都有 `type`／`ts`／`task_id`／`mode`（`REQUIRED`）。

| 欄位 | 值 | 意思 |
|---|---|---|
| `mode` | `"live"`／`"replay"` | `live`＝這一刻正在真跑；`replay`＝**重播錄下來的那一份**。電視用它在畫面上標「重播」（CLAUDE.md 展場硬約束 1：畫面上必須講明） |
| `arm` | `"ON"`／`"OFF"` | 同一格兩串事件：有 Vacant 的那一臂與關掉的那一臂 |
| `ts` | ISO 8601、毫秒、UTC | 單調不減；電視的去重鍵 `ts|type|task_id|arm|reviewer` 靠它 |

`type` 白名單（`EMITTED`）與各自的欄位：

| type | 臂 | 何時 | 主要欄位 |
|---|---|---|---|
| `task_opened` | ON | 一格開始 | `prompt`、`prompt_sha256`、`evidence`（恆 `null`，要跑完才推得出）、`stratum` |
| `routed` | ON | 一格開始 | `worker`、`basis`（恆 `"random"`）、`basis_note` |
| `working` | ON／OFF | **每一通**經過中介的模型呼叫 | `worker`、`attempt`、`calls_so_far`（這一跑到目前為止的通數，正整數） |
| `revised` | ON | 第 2 次以後的嘗試**真的開始了** | `reviser`（＝同一個 worker）、`transition`、`retry_arm`、`attempt` |
| `draft_done` | ON／OFF | agent 行程結束 | `calls_used`、`attempt`、`feedback_bytes`、`feedback_delivery`、`timed_out` |
| `gate_ran` | **只有 ON** | 閘門跑完 | `passed`、`n_tests`、`failed_case`、`attempt` |
| `verdict` | ON／OFF | 一跑結束 | `accepted`（三值）、`meets_demand`（恆 `null`）、`blocked_by`、`stop_reason`、`evidence` |
| `receipt` | **只有 ON** | 簽了收據 | `sha256`＝`chain_head`、`verify_url`、`prompt_sha256` |

⚠ **2026-09-24 起不再發的兩種**（它們只能從 run 目錄事後推，lifecycle 裡沒有）：
`counters`（整批累計）與 `postaudit`（OFF 臂的事後稽核）。**不發不是忘了發**：
誰要它們回來，得先讓 Vacant 在跑的當下把它寫進 lifecycle，不准在這裡另開一條推導。

## 誠實規則（`validate` 是它的可執行版本）

1. **沒發生的步驟不發事件。** `vacant run` 沒有同儕評審、沒有抽樣稽核
   ⇒ `review_vote`／`audited` 一個都不准出現（`NEVER`）。
2. `routed.basis` 恆為 `"random"`：`vacant run` 沒有路由層，誰做這一格是人指定的。
3. `verdict.meets_demand` 恆為 `null`：要隱藏測資才答得出來，而隱藏測資不進展件。
4. `verdict.accepted` 是**三值**：`true`／`false`／`null`（沒量）。`ungated` 配布林＝說謊。
5. **OFF 臂沒有閘門、不簽收據、沒有裁決**：不發 `gate_ran`、不發 `receipt`、
   `accepted` 恆為 `null`。
6. 每一格開了（`task_opened`）就一定要走到 `verdict`——否則電視的佇列卡死
   （它只看 `pending[0]`）。重播與輪播端保證「過不了就不播」，現場真跑見
   `live_events` 誠實邊界 6。
7. 去重鍵不准撞：撞了那一格會被電視靜靜吃掉。
8. **事件流本身沒有簽章。** 可驗的那一份是收據頁（`/r/<cell>`）。電視是展示端不是證據端。
"""
from __future__ import annotations

from datetime import datetime, timezone

#: 每個事件都必須有的欄位。`mode` 是 2026-09-24 加的（重播要在畫面上講明）。
REQUIRED = ("type", "ts", "task_id", "mode")

#: `mode` 的兩個值。**沒有第三個**：「模擬」那種東西不走這條線。
MODE_LIVE, MODE_REPLAY = "live", "replay"
MODES = (MODE_LIVE, MODE_REPLAY)

#: 生產端發得出來的 type。沒列在這裡的一律不發（誠實規則：沒發生就不發）。
EMITTED = ("task_opened", "routed", "working", "draft_done", "gate_ran",
           "revised", "verdict", "receipt")

#: 事件的 `arm` 欄位。一格有兩串事件（有 Vacant／關掉 Vacant）。
ARM_ON, ARM_OFF = "ON", "OFF"
ARMS = (ARM_ON, ARM_OFF)

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
#: 兩條臂的差別**就是**實驗處理本身，不可以共用一句話。
TRANSITION = {
    "revise": "gate_fail→revise：保留工作區，把可見驗收的失敗原文寫進 "
              "VACANT_FEEDBACK.md，同一個 agent 再跑一次",
    "resample": "gate_fail→resample：工作區重置回起點（含 .git），"
                "不給失敗原文，同一個 agent 重跑一次",
    "none": "沒有重試臂（--retry none）",
}


def iso(ms: int) -> str:
    """毫秒 → ISO 8601（UTC、**固定到毫秒**）。

    固定精度是為了讓 `ts` 的**字串比較**等於時間比較（`validate` 用字串比單調性，
    電視的去重鍵也是字串）。不固定的話 `…:00+00:00` 與 `…:00.001000+00:00`
    的長度不同，比較結果只是剛好對。
    """
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(
        timespec="milliseconds")


def cell_verify_url(template: str, cell_id: str) -> str:
    """`verify_url` 的 per-cell 版（C4）。

    ⚠ 全批共用一個字串是舊版的錯：觀眾在電視上看到第 7 格，手機打開收據頁卻落在
    第 1 格。`{cell}` 佔位符讓每一格指到自己那一頁；沒有佔位符就原樣用
    （離線 `file://` 直開整頁的那種用法仍然成立）。
    """
    return template.replace("{cell}", cell_id) if "{cell}" in template else template


def dedup_key(e: dict) -> str:
    """電視的去重鍵（`LIVE_INTERFACE.md` §一）。撞鍵 ⇒ 那一筆被靜靜吃掉。"""
    return "%s|%s|%s|%s|%s" % (e.get("ts"), e.get("type"), e.get("task_id"),
                               e.get("arm", ""), e.get("reviewer", ""))


def _is_pos_int(v) -> bool:
    # ⚠ `isinstance(True, int)` 為真：布林要先踢掉（attest 的同一條防呆）。
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def validate(evs: list[dict], *, require_settled: bool = True) -> list[str]:
    """契約自檢。回傳問題清單（空＝合格）。

    `require_settled=False`：給**還在跑**的片段用（現場 tail 到一半）——
    那時「開了還沒 verdict」是正常的，其餘規則照樣咬。
    """
    bad = []
    last = ""
    for i, e in enumerate(evs):
        n = i + 1
        for k in REQUIRED:
            if k not in e:
                bad.append(f"第 {n} 個事件缺欄位 {k}")
        t = e.get("type")
        if t in NEVER:
            bad.append(f"第 {n} 個事件是這條路上不存在的層：{t!r}")
        elif t not in EMITTED:
            bad.append(f"第 {n} 個事件的 type 不在白名單：{t!r}")
        if "mode" in e and e.get("mode") not in MODES:
            bad.append(f"第 {n} 個事件的 mode 是 {e.get('mode')!r}，只能是 live／replay")
        if "arm" in e and e.get("arm") not in ARMS:
            bad.append(f"第 {n} 個事件的 arm 是 {e.get('arm')!r}，只能是 ON／OFF")
        ts = e.get("ts", "")
        if not isinstance(ts, str):
            bad.append(f"第 {n} 個事件的 ts 不是字串")
            ts = last
        if ts < last:
            bad.append(f"第 {n} 個事件的 ts 比前一個早")
        last = ts or last
        # 「沒量」不可以在資料上長成「量到沒過」（規則 4）。
        if t == "verdict":
            if e.get("accepted") not in (True, False, None):
                bad.append(f"第 {n} 個事件：accepted 只能是 true／false／null")
            if e.get("stop_reason") == "ungated" and e.get("accepted") is not None:
                bad.append(f"第 {n} 個事件：`ungated`（沒量）卻給了 accepted 布林值")
            if e.get("meets_demand") is not None:
                bad.append(f"第 {n} 個事件：meets_demand 只能是 null"
                           "（要隱藏測資才答得出來，而隱藏測資不進展件）")
            if e.get("blocked_by") == "review":
                bad.append(f"第 {n} 個事件：blocked_by=review——這條路上沒有評審層")
        if t == "routed" and e.get("basis") != "random":
            bad.append(f"第 {n} 個事件：basis 不是 random（`vacant run` 沒有路由層）")
        if t == "revised" and e.get("reviser") is None:
            bad.append(f"第 {n} 個事件：revised 沒有 reviser")
        if t == "working":
            for k in ("arm", "worker", "attempt", "calls_so_far"):
                if k not in e:
                    bad.append(f"第 {n} 個事件：working 缺欄位 {k}")
            if not _is_pos_int(e.get("calls_so_far")):
                bad.append(f"第 {n} 個事件：working.calls_so_far 要是正整數，"
                           f"拿到 {e.get('calls_so_far')!r}")
        # ── 反事實那一臂的三條硬規則（規則 5）────────────────────────
        if e.get("arm") == ARM_OFF:
            if t == "gate_ran":
                bad.append(f"第 {n} 個事件：OFF 臂發了 gate_ran——"
                           "**那一臂沒有閘門**，發了就是把「沒有這一層」"
                           "演成「這一層也判了」")
            if t == "receipt":
                bad.append(f"第 {n} 個事件：OFF 臂發了 receipt——"
                           "**那一臂不簽收據**，觀眾在這一邊沒有東西可以自己重驗")
            if t == "verdict" and e.get("accepted") is not None:
                bad.append(f"第 {n} 個事件：OFF 臂的 accepted 不是 null——"
                           "那一臂不驗收也不拒交，沒有裁決可言")
    keys = [dedup_key(e) for e in evs]
    if len(set(keys)) != len(keys):
        bad.append("有事件撞到電視的去重鍵，會被靜靜吃掉一格")
    if require_settled:
        # 每一格都要走到 verdict，否則電視的 liveAssemble 會一直等
        # （而且會**卡住整個佇列**：它只看 pending[0] 的 task_id）。
        # ⚠ **逐臂**收尾，不是逐格：ON 那一跑斷在半路、OFF 那一跑有 verdict 的格子，
        #   逐格看是「有 verdict」，實際上 ON 那一串永遠等不到收尾（2026-09-24
        #   測試抓到：舊版只比 task_id，這種格子會被當成完整的播出去）。
        #   `task_opened`／`routed` 沒有 `arm` 欄位，它們是 ON 那一串的開頭。
        opened = set()
        for e in evs:
            tid = e.get("task_id")
            if tid is None or e.get("type") == "verdict":
                continue
            arm = e.get("arm") or (ARM_ON if e.get("type") in ("task_opened", "routed")
                                   else None)
            if arm in ARMS:
                opened.add((tid, arm))
        settled = {(e.get("task_id"), e.get("arm")) for e in evs
                   if e.get("type") == "verdict"}
        for tid, arm in sorted(opened - settled):
            bad.append(f"{tid}（{arm}）開了但沒有 verdict：電視會一直等這一格"
                       "（整個佇列卡住）")
    return bad
