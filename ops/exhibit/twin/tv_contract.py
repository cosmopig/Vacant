"""twin/tv_contract — 電視（人類動物園 `world3`）吃的 world event 契約：常數＋可執行自檢。

## 這支在架構裡承重什麼

展場只剩一條路（2026-09-24 人類裁決「刪事後推導，留錄影重播」）：

```
 vacant run --events ──lifecycle.jsonl──▶ live_events.Folder ──world event──▶ 電視 ?live=
   （現場真跑，或錄下來的那一份）           唯一一支轉換器          這一支定的契約
```

**這一支不產生任何事件。** 它只定「電視事件長什麼樣、哪些話不准說」，
產生事件的只有 `live_events.Folder`（現場真跑與重播錄影走同一支；吃 lifecycle 與
分身的旁註）＋ `live_events.Tally`（`counters`，播放端依已經寫出去的事件數的）。
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
| `task_opened` | ON | 一格開始 | `prompt`、`prompt_sha256`、`evidence`（恆 `null`，要跑完才推得出）、`stratum`、`task_kind`（見下） |
| `routed` | ON | 一格開始 | `worker`、`basis`（恆 `"random"`）、`basis_note` |
| `working` | ON／OFF | **每一通**經過中介的模型呼叫 | `worker`、`attempt`、`calls_so_far`（這一跑到目前為止的通數，正整數） |
| `revised` | ON | 第 2 次以後的嘗試**真的開始了** | `reviser`（＝同一個 worker）、`transition`、`retry_arm`、`attempt` |
| `draft_done` | ON／OFF | agent 行程結束 | `calls_used`、`attempt`、`feedback_bytes`、`feedback_delivery`、`timed_out` |
| `gate_ran` | **只有 ON** | 閘門跑完 | `passed`、`n_tests`、`failed_case`、`attempt`；分身的自主任務另帶 `checks[{id,ok,label,file?,line?}]`（規則 11） |
| `verdict` | ON／OFF | 一跑結束 | `accepted`（三值）、`meets_demand`（恆 `null`）、`blocked_by`、`stop_reason`、`evidence` |
| `receipt` | **只有 ON** | 簽了收據 | `sha256`＝`chain_head`、`verify_url`、`prompt_sha256` |
| `postaudit` | **只有 OFF** | 分身事後補量 OFF 的交付 | `when`＝`"after_the_run"`、`is_verdict`＝`false`、`signed`＝`false`、`all_pass`、`passed`、`n_tests`、`failed_case`、`ruler`、`note` |
| `counters` | —（`task_id`＝`"-"`） | 每一筆 `verdict`／`postaudit` 寫出去之後 | 見下 |

### `postaudit` 與 `counters` 從哪來（2026-09-24 人類裁決「分身側自己記一份補回」）

這兩種**不是 Vacant 當場做的事**，所以**不在 lifecycle 裡**，也不准進去：

- `postaudit` 的來源是分身自己的旁註串流 `twin.sidecar/1`（`sidecar.py`，
  `run_twin.postaudit_off` 完成當下寫的），由同一支 `live_events.Folder` 轉出。
  它**只在綁得上那一跑**（`run_id`＋`ws_end_sha256`）時才發；舊錄影沒有旁註
  ⇒ 電視上就沒有 `postaudit`，**不補、不猜**。
- `counters` 是 `serve_twin` 依**已經寫進事件檔的格子**當場數的（`live_events.Tally`），
  重播與現場**分開數**（各帶自己的 `mode`），同一格播第二次不重複算。
  欄位：`total`／`blocked`／`delivered`／`evidence_counts`（ON 臂）、
  `off_ran`／`off_with_receipt`／`off_counters_note`（播過 OFF 才有）、
  `off_postaudited`／`off_postaudit_not_all_pass`（播過 postaudit 才有）。
  **沒量到的欄位不發**：`audited`（沒有抽樣稽核層）、`on_leaked`／`off_leaked`
  （要隱藏測資才答得出來）永遠不發（`COUNTERS_NEVER`）。

### `task_kind`（2026-09-24）：這一格是哪一種任務

| 值 | 意思 | 從哪來 |
|---|---|---|
| `"code"` | 反事實題庫格：有驗收套件（閘門）、同一題有 ON／OFF 兩臂 | `run_twin.py` 的 `caller.task_kind` |
| `"practical"` | 觀眾分身**自己決定**的實務任務：沒有客觀標準、只有 ON 一臂、`accepted` 恆 `null` | `twinagent.py` 的 `caller.task_kind` |
| （缺席） | 當 `"code"`：2026-09-24 之前的錄影沒有這個欄位 | — |

⚠ **缺席只給舊錄影用。** 新的東西（現場 tail、新錄的錄影）一律要帶——
`validate(require_task_kind=True)`；`serve_twin` 的 `--live` 那條路與
`record_fixture.sh` 都開著它。`practical` 那一格的 `task_id` ＝ `twin_id`，
電視拿它對 twinlink 的 `people[].twin_id`；**事件流裡沒有他的決定、沒有他的名字**。

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
9. **`postaudit` 永遠不長得像裁決**：`when="after_the_run"`、`is_verdict=false`、
   `signed=false` 三個旗標缺一不可，而且只准出現在 OFF 臂。
10. **`counters` 不准有這條路上不存在的層**（`COUNTERS_NEVER`），數字欄位是非負整數。
11. **分身的自主任務（`task_kind="practical"`）沒有「對錯」的客觀標準，但交件前有「有沒有根據」的閘門**
    （第 2 版，2026-10-01，裁決 `DECISION_20261001_TWIN_GROUNDING_GATE.md`；第 1 版——practical 格
    不准有 `gate_ran`／`revised`、`accepted` 恆 `null`——只活在 2026-09-24～10-01 的錄影裡，
    舊錄影照驗：沒有 `gate_ran` 就是 `ungated`／`null`）：
    那一格不准有 OFF 臂；`gate_ran`／`revised` 允許（閘門就是 `vacant run` 的閘門，重改就是它的
    `revise` 臂）；`gate_ran.checks[]` 每條只准 `id`／`ok`／`label`／`file`／`line`
    （`file`＝`artifact`｜`plan`、`line`＝正整數；**不帶檔名、不帶內容**），`passed`＝所有 `ok` 的 AND；
    `verdict.accepted` 與 `stop_reason` 對得上：`visible_pass`⇒`true`、`attempts_exhausted`⇒`false`
    （照常交件、照實標出）、`ungated`／`infra_void`⇒`null`。
    **不准發明評分**——閘門只問「根據有沒有」，不問好不好；Vacant 在這一格保證的是
    「每一通模型呼叫都經過中介、行程結束時簽了收據、`accepted` 說的只是有沒有根據」。
"""
from __future__ import annotations

from datetime import datetime, timezone

#: 每個事件都必須有的欄位。`mode` 是 2026-09-24 加的（重播要在畫面上講明）。
REQUIRED = ("type", "ts", "task_id", "mode")

#: `mode` 的兩個值。**沒有第三個**：「模擬」那種東西不走這條線。
MODE_LIVE, MODE_REPLAY = "live", "replay"
MODES = (MODE_LIVE, MODE_REPLAY)

#: 生產端發得出來的 type。沒列在這裡的一律不發（誠實規則：沒發生就不發）。
#: `postaudit`／`counters` 在 2026-09-24 拿掉又加回來：來源換成分身自己的旁註
#: （`sidecar.py`）與 `serve_twin` 的當場累計，**不是** lifecycle、**不是**事後推導。
#: `twin_step`（2026-09-28）同一條路：來源是分身的旁註，不是 lifecycle。
EMITTED = ("task_opened", "routed", "working", "draft_done", "gate_ran",
           "revised", "verdict", "receipt", "postaudit", "counters", "twin_step", "twin_say",
           "twin_fortune")

#: `postaudit.when` 唯一合法的值（與 `sidecar.WHEN_AFTER` 同值，測試釘住）。
WHEN_AFTER = "after_the_run"

#: `counters` 裡**永遠不准出現**的欄位：這條路上沒有這一層，或要隱藏測資才答得出來。
#: 發一個 `audited: 0` 就是把「沒有這一層」畫成「有這一層，只是這次沒抽中」。
COUNTERS_NEVER = ("audited", "on_leaked", "off_leaked")

#: `counters` 的整數欄位（`evidence_counts` 另外驗）。
COUNTERS_INT = ("total", "blocked", "delivered", "off_ran", "off_with_receipt",
                "off_postaudited", "off_postaudit_not_all_pass")

#: 事件的 `arm` 欄位。一格有兩串事件（有 Vacant／關掉 Vacant）。
ARM_ON, ARM_OFF = "ON", "OFF"
ARMS = (ARM_ON, ARM_OFF)

#: `task_opened.task_kind` 的兩個值（見模組 docstring）。缺席＝舊錄影＝當 code。
KIND_CODE, KIND_PRACTICAL = "code", "practical"
TASK_KINDS = (KIND_CODE, KIND_PRACTICAL)

#: 分身那一格的 `routed.basis_note`。**沒有派工**：這一格是觀眾自己的分身。
PRACTICAL_BASIS_NOTE = ("這一格是觀眾自己的數位分身：沒有派工，"
                        "做什麼是分身自己決定的")
#: 分身那一格的 `verdict.accepted_note`。`null` 不是「沒過」。
#: ⚠ 口徑：講「經過中介」「簽了收據」，**不講「信任」、不講「驗證了它做得好」**。
PRACTICAL_ACCEPTED_NOTE = ("這類任務沒有客觀標準——Vacant 不判對錯；它保證的是"
                           "每一通模型呼叫都經過中介、行程結束時簽了收據")
#: 分身那一格 `verdict.accepted` 是布林時的那一句：`true`／`false` 只說「每一步有沒有根據」。
#: ⚠ 口徑：不講「信任」、不講「做得好」；`false` 照常交件（拍立得照發）、照實標出沒有根據的位置。
PRACTICAL_GROUNDING_NOTE = ("Vacant 不判對錯；這一格查的是每一步有沒有根據，"
                            "accepted 說的只是這個——沒過的照常交件、照實標出位置")
#: 規則 11 的版號：1＝2026-09-24（practical 格沒有閘門、`accepted` 恆 null）；
#: 2＝2026-10-01（有「根據」閘門與重改，`accepted` 三值）。電視端文件 `LIVE_INTERFACE.md` §十／§十一
#: 的 v8／v9 就是第 2 版的消費端。
RULE11_VERSION = 2
#: 分身那一格 `verdict.stop_reason` 只准是這幾個，以及各自對應的 `accepted`。
PRACTICAL_STOPS = ("ungated", "infra_void", "visible_pass", "attempts_exhausted")
PRACTICAL_ACCEPTED_FOR = {"ungated": None, "infra_void": None,
                          "visible_pass": True, "attempts_exhausted": False}
#: `gate_ran.checks[]` 每條准出現的欄位（兩份契約逐字相同：`LIVE_INTERFACE.md` §十、§十一）。
GATE_CHECK_KEYS = ("id", "ok", "label", "file", "line")
GATE_CHECK_FILES = ("artifact", "plan")
GATE_CHECK_LABEL_MAX = 80
#: 被時限切掉的嘗試：四格 `ok` 都是 `null`（未判），label 固定這一句（與 `grounding_gate.TIMEOUT_LABEL` 同值，
#: 測試釘住）。電視看 `draft_done.timed_out` 演「時間到」，不演成四個錯。
GATE_CHECK_TIMEOUT_LABEL = "時間到，這一次沒有交件"

#: `twin_step.step` 的白名單（`sidecar.STEP_KINDS` 同值，兩邊測試釘住）。
TWIN_STEPS = ("read", "write", "list")
#: `twin_step.path_kind` 的白名單（`sidecar.PATH_KINDS` 同值）。
TWIN_GROUND_KINDS = tuple("ground:" + c for c in (
    "drop", "clay", "longtable", "gate", "chain", "draft", "cards", "easel"))
TWIN_PATH_KINDS = ("traits", "plan", "artifact", "other") + TWIN_GROUND_KINDS
#: `twin_fortune`（P10，2026-10-02）：分身這一跑用的命盤。**全是枚舉**（與 `sidecar.FORTUNE_*` 同值，測試釘住）；
#: `lines` 只在 `phase == "card"` 才有，≤3 句、每句 ≤60 字、已逐句對過步驟紀錄。不帶檔名、不帶星座名與觀眾原文。
FORTUNE_PHASES = ("way", "card")
FORTUNE_MBTI = ("INFP", "INFJ", "INTP", "INTJ", "ISFP", "ISFJ", "ISTP", "ISTJ",
                "ENFP", "ENFJ", "ENTP", "ENTJ", "ESFP", "ESFJ", "ESTP", "ESTJ")
FORTUNE_SOURCES = ("ai", "self", "twin")
FORTUNE_ELEMENTS = ("火", "土", "風", "水")
FORTUNE_BLOODS = ("A", "B", "O", "AB")
FORTUNE_MAX_LINES = 3
FORTUNE_LINE_MAX = 60
#: `twin_fortune` 不准帶的欄位（本體是上面那幾個枚舉與 `lines`）。
FORTUNE_FORBIDDEN = ("path", "name", "file", "content", "text", "zodiac", "card_text")


def fortune_event_problems(e: dict, n: int) -> list[str]:
    """一筆 `twin_fortune` 事件的形狀自檢（`validate` 與 `live_events` 共用）。回問題清單。"""
    bad: list[str] = []
    if e.get("phase") not in FORTUNE_PHASES:
        bad.append(f"第 {n} 個事件：twin_fortune.phase 不在白名單：{e.get('phase')!r}")
    if not (isinstance(e.get("attempt"), int) and not isinstance(e.get("attempt"), bool) and e["attempt"] >= 1):
        bad.append(f"第 {n} 個事件：twin_fortune.attempt 要是 ≥ 1 的整數")
    for key, allowed in (("mbti", FORTUNE_MBTI), ("mbti_source", FORTUNE_SOURCES),
                         ("element", FORTUNE_ELEMENTS), ("blood", FORTUNE_BLOODS)):
        v = e.get(key)
        if v is not None and v not in allowed:
            bad.append(f"第 {n} 個事件：twin_fortune.{key} 不在白名單：{v!r}")
    if (e.get("mbti") is None) != (e.get("mbti_source") is None):
        bad.append(f"第 {n} 個事件：twin_fortune 的 mbti 與 mbti_source 要同時有或同時沒有")
    ls = e.get("lines")
    if not isinstance(ls, list) or len(ls) > FORTUNE_MAX_LINES:
        bad.append(f"第 {n} 個事件：twin_fortune.lines 要是 ≤ {FORTUNE_MAX_LINES} 句的清單")
    else:
        if e.get("phase") == "way" and ls:
            bad.append(f"第 {n} 個事件：twin_fortune 的 way 拍不帶 lines")
        for s in ls:
            if not isinstance(s, str) or not s.strip() or len(s) > FORTUNE_LINE_MAX:
                bad.append(f"第 {n} 個事件：twin_fortune.lines 每句要是非空字串、≤ {FORTUNE_LINE_MAX} 字")
    for k in FORTUNE_FORBIDDEN:
        if k in e:
            bad.append(f"第 {n} 個事件：twin_fortune 帶了 {k!r}")
    return bad


#: `twin_say.text` 的字數上限（`sidecar.SAY_MAX` 同值，測試釘住；契約補充 §E）。
TWIN_SAY_MAX = 80
#: `twin_say` 不准帶的欄位（它的本體就是 `text`，其餘內容欄位照擋）。
TWIN_SAY_FORBIDDEN = ("path", "name", "file", "content", "code", "args", "arguments")

#: `twin_step` 不准帶的欄位——它是**不帶檔名**那一份，跟 `sidecar.CONTENT_KEYS`
#: 同一條規則，這裡是電視事件那一層的第二道網。
TWIN_STEP_FORBIDDEN = ("path", "name", "file", "text", "content")

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


def _is_nat(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def task_kinds(evs: list[dict]) -> dict[str, str]:
    """`task_id` → `task_kind`（只看 `task_opened`；缺席的當 `code`）。"""
    return {e.get("task_id"): (e.get("task_kind") or KIND_CODE)
            for e in evs if e.get("type") == "task_opened"}


def validate(evs: list[dict], *, require_settled: bool = True,
             require_task_kind: bool = False) -> list[str]:
    """契約自檢。回傳問題清單（空＝合格）。

    `require_settled=False`：給**還在跑**的片段用（現場 tail 到一半）——
    那時「開了還沒 verdict」是正常的，其餘規則照樣咬。
    `require_task_kind=True`：新的東西（現場、新錄影）的 `task_opened` 一定要帶
    `task_kind`；缺席只給 2026-09-24 之前的舊錄影。
    ⚠ 規則 11 只咬**同一批裡看得到 `task_opened`** 的格子：現場 tail 是一段一段驗的，
      後面幾段看不到開頭，那幾段的把關靠生產端（`live_events.Folder`）本身不發。
    """
    bad = []
    last = ""
    kinds = task_kinds(evs)
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
        if t == "task_opened":
            if "task_kind" in e and e.get("task_kind") not in TASK_KINDS:
                bad.append(f"第 {n} 個事件：task_kind 是 {e.get('task_kind')!r}，"
                           f"只能是 {'／'.join(TASK_KINDS)}")
            elif require_task_kind and "task_kind" not in e:
                bad.append(f"第 {n} 個事件：task_opened 沒有 task_kind——"
                           "缺席只給舊錄影；新的東西要講明是題庫格還是分身的自主任務")
        # ── 分身的自主任務（規則 11，第 2 版）：沒有對照、有「根據」閘門 ─────
        if kinds.get(e.get("task_id")) == KIND_PRACTICAL:
            if e.get("arm") == ARM_OFF:
                bad.append(f"第 {n} 個事件：分身的自主任務出現 OFF 臂——"
                           "那一格沒有反事實對照，畫面上不准長出一個")
            if t == "verdict":
                sr = e.get("stop_reason")
                if sr not in PRACTICAL_STOPS:
                    bad.append(f"第 {n} 個事件：分身的自主任務 stop_reason 是 "
                               f"{sr!r}，只能是 {'／'.join(PRACTICAL_STOPS)}")
                elif e.get("accepted") is not PRACTICAL_ACCEPTED_FOR[sr]:
                    bad.append(f"第 {n} 個事件：分身的自主任務 stop_reason={sr!r} 時 "
                               f"accepted 只能是 {PRACTICAL_ACCEPTED_FOR[sr]!r}，"
                               f"拿到 {e.get('accepted')!r}")
        if t == "gate_ran" and "checks" in e:
            # 同一批看不到 task_opened（現場 tail 的後段）就不咬——與規則 11、twin_step 同一個口徑；
            # 2026-10-02 展場第一跑：咬了 ⇒ gate_ran 被丟、之後整格斷在「它說做完了」。
            _tk = kinds.get(e.get("task_id"))
            if _tk is not None and _tk != KIND_PRACTICAL:
                bad.append(f"第 {n} 個事件：只有分身的自主任務的 gate_ran 才帶 checks"
                           "（題庫格的閘門沒有逐格窗）")
            ck = e.get("checks")
            if not isinstance(ck, list) or not ck:
                bad.append(f"第 {n} 個事件：gate_ran.checks 要是非空清單（沒有就不要帶這個欄位）")
            else:
                for j, c in enumerate(ck, 1):
                    if not isinstance(c, dict):
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條不是物件")
                        continue
                    extra = sorted(set(c) - set(GATE_CHECK_KEYS))
                    if extra:
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條帶了不准的欄位 {extra}")
                    if not (isinstance(c.get("id"), str) and c["id"]):
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條的 id 要是非空字串")
                    if c.get("ok") is None:
                        if c.get("label") != GATE_CHECK_TIMEOUT_LABEL or "line" in c or "file" in c:
                            bad.append(f"第 {n} 個事件：checks 第 {j} 條 ok:null（未判）只准用於時間到，"
                                       f"label 要是「{GATE_CHECK_TIMEOUT_LABEL}」且不帶位置")
                    elif not isinstance(c.get("ok"), bool):
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條的 ok 要是布林（或時間到的 null）")
                    lb = c.get("label")
                    if not (isinstance(lb, str) and lb.strip()
                            and len(lb) <= GATE_CHECK_LABEL_MAX):
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條的 label 要是非空短句"
                                   f"（≤ {GATE_CHECK_LABEL_MAX} 字）")
                    if "file" in c and c["file"] not in GATE_CHECK_FILES:
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條的 file 只能是 "
                                   f"{'／'.join(GATE_CHECK_FILES)}")
                    if "line" in c and not _is_pos_int(c["line"]):
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條的 line 要是正整數")
                    if ("line" in c) != ("file" in c):
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條的 file 與 line 要一起出現")
                    if c.get("ok") is True and ("line" in c or "file" in c):
                        bad.append(f"第 {n} 個事件：checks 第 {j} 條通過了卻帶位置")
                if all(isinstance(c, dict) and c.get("ok") in (True, False, None) for c in ck) \
                        and isinstance(e.get("passed"), bool) \
                        and e["passed"] != all(c["ok"] is True for c in ck):
                    bad.append(f"第 {n} 個事件：gate_ran.passed 與 checks 的逐條結果對不上")
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
            if "error" in e and not isinstance(e["error"], bool):
                bad.append(f"第 {n} 個事件：working.error 要是布林，拿到 {e['error']!r}")
        # ── 分身的步驟事件：不帶檔名、白名單、只在 ON／practical 那一格 ──
        if t == "twin_step":
            if e.get("arm") != ARM_ON:
                bad.append(f"第 {n} 個事件：twin_step 的 arm 不是 ON"
                           "（分身的步驟只在 ON 臂發生）")
            tk = kinds.get(e.get("task_id"))
            if tk is not None and tk != KIND_PRACTICAL:
                bad.append(f"第 {n} 個事件：twin_step 出現在非分身自主任務的格子"
                           "（反事實題庫格沒有這一欄）")
            if e.get("step") not in TWIN_STEPS:
                bad.append(f"第 {n} 個事件：twin_step.step 不在白名單："
                           f"{e.get('step')!r}")
            if e.get("path_kind") not in TWIN_PATH_KINDS:
                bad.append(f"第 {n} 個事件：twin_step.path_kind 不在白名單："
                           f"{e.get('path_kind')!r}")
            bv = e.get("bytes")
            if bv is not None and not _is_nat(bv):
                bad.append(f"第 {n} 個事件：twin_step.bytes 要是非負整數或 null")
            if "ok" in e and not isinstance(e["ok"], bool):
                bad.append(f"第 {n} 個事件：twin_step.ok 要是布林，拿到 {e['ok']!r}")
            for k in TWIN_STEP_FORBIDDEN:
                if k in e:
                    bad.append(f"第 {n} 個事件：twin_step 帶了 {k!r}——"
                               "這一份事件流不帶檔名")
        # ── 分身自己說的話：只在 ON／practical、≤80 字、不帶檔名／程式碼欄位 ──
        if t == "twin_say":
            if e.get("arm") != ARM_ON:
                bad.append(f"第 {n} 個事件：twin_say 的 arm 不是 ON")
            tk = kinds.get(e.get("task_id"))
            if tk is not None and tk != KIND_PRACTICAL:
                bad.append(f"第 {n} 個事件：twin_say 出現在非分身自主任務的格子"
                           "（反事實題庫格沒有這一欄）")
            tx = e.get("text")
            if not isinstance(tx, str) or not tx.strip():
                bad.append(f"第 {n} 個事件：twin_say.text 要是非空字串")
            elif len(tx) > TWIN_SAY_MAX:
                bad.append(f"第 {n} 個事件：twin_say.text 超過 {TWIN_SAY_MAX} 字")
            if not isinstance(e.get("truncated"), bool):
                bad.append(f"第 {n} 個事件：twin_say.truncated 只能是 true／false")
            for k in ("seq", "turn"):
                if not _is_nat(e.get(k)):
                    bad.append(f"第 {n} 個事件：twin_say.{k} 要是非負整數")
            for k in TWIN_SAY_FORBIDDEN:
                if k in e:
                    bad.append(f"第 {n} 個事件：twin_say 帶了 {k!r}")
        # ── 命盤（P10）：只在 ON／practical、全是枚舉 ──────────────────
        if t == "twin_fortune":
            if e.get("arm") != ARM_ON:
                bad.append(f"第 {n} 個事件：twin_fortune 的 arm 不是 ON")
            tk = kinds.get(e.get("task_id"))
            if tk is not None and tk != KIND_PRACTICAL:
                bad.append(f"第 {n} 個事件：twin_fortune 出現在非分身自主任務的格子")
            bad.extend(fortune_event_problems(e, n))
        # ── 事後稽核不准長得像裁決（規則 9）：三個旗標缺一不可 ────────
        if t == "postaudit":
            if e.get("is_verdict") is not False or e.get("signed") is not False:
                bad.append(f"第 {n} 個事件：postaudit 必須自己說 "
                           "`is_verdict=false`＋`signed=false`，"
                           "否則它與當場的裁決在資料上分不開")
            if e.get("when") != WHEN_AFTER:
                bad.append(f"第 {n} 個事件：postaudit 沒說它是事後量的"
                           f"（when 必須是 {WHEN_AFTER!r}）")
            if e.get("arm") != ARM_OFF:
                bad.append(f"第 {n} 個事件：postaudit 只准出現在 OFF 臂"
                           "（ON 臂有當場的閘門，不需要事後補量）")
            if not isinstance(e.get("all_pass"), bool):
                bad.append(f"第 {n} 個事件：postaudit.all_pass 只能是 true／false")
        # ── 累計不准有不存在的層（規則 10）────────────────────────────
        if t == "counters":
            for k in COUNTERS_NEVER:
                if k in e:
                    bad.append(f"第 {n} 個事件：counters 帶了 {k!r}——"
                               "這條路上沒有這一層（或要隱藏測資才答得出來）")
            for k in COUNTERS_INT:
                if k in e and not _is_nat(e[k]):
                    bad.append(f"第 {n} 個事件：counters.{k} 要是非負整數，"
                               f"拿到 {e[k]!r}")
            ec = e.get("evidence_counts")
            if ec is not None and not (isinstance(ec, dict) and all(
                    _is_pos_int(v) for v in ec.values())):
                bad.append(f"第 {n} 個事件：counters.evidence_counts 要是 等級→正整數")
            if "off_postaudit_not_all_pass" in e and not (
                    _is_nat(e.get("off_postaudited"))
                    and _is_nat(e["off_postaudit_not_all_pass"])
                    and e["off_postaudit_not_all_pass"] <= e["off_postaudited"]):
                bad.append(f"第 {n} 個事件：off_postaudit_not_all_pass 沒有對應的"
                           "（或比它小的）off_postaudited")
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
