"""twin/live_events — `vacant.lifecycle/1` 事件流 → 電視吃的 world event。**唯一的一支轉換器。**

## 這支在架構裡承重什麼

2026-09-24 人類裁決「刪事後推導，留錄影重播」：展場只剩一條路。

```
 vacant run（pi／OpenCode／…）──lifecycle.jsonl──▶ Folder（這一支）──events.jsonl──▶ 電視 ?live=
      觀察到的人當場寫                只認 lifecycle 契約     tv_contract.py
```

- **現場真跑**：`run_twin.py --events` 一邊跑一邊寫 lifecycle，這一支 tail 它
  （或 `serve_twin.py --live` 內建 tail），`mode="live"`。
- **離線備援**：重播**錄下來的** lifecycle.jsonl（`ops/exhibit/twin/recordings/`），
  走**同一個 `Folder`**，`mode="replay"`。重播與現場的差別只有兩個：
  `mode` 那一欄、以及 `ts` 是重播當下的牆鐘（見 `serve_twin` 的節奏規則）。

在此之前還有第二條路：`to_events.py` 等一跑結束，讀 run 目錄的內臟推回事件。
那一條**已經刪掉**——兩條路講同一件事要靠一條對照測試撐著，而 Vacant 每改一次
落盤格式，推導的那一條就得跟著改、改漏了畫面就說錯。現在分身只認
`vacant_network/vrun/lifecycle.py` 那一份契約；契約版號（`SCHEMA`）變了
`Folder.feed()` 會大聲拒絕，不會安靜地演錯。

電視事件的欄位與誠實規則寫在 `tv_contract.py`（常數＋`validate`）。

## 對照表（lifecycle → 電視）

| lifecycle | 臂 | 電視事件 |
|---|---|---|
| `run_started` | ON | `task_opened` ＋ `routed` |
| `run_started` | OFF | （不發：OFF 那一串從 `draft_done` 開始） |
| `model_call` | ON／OFF | `working`（`calls_so_far`＝這一跑到目前為止的通數） |
| `attempt_started`（第 2 次以後） | ON | `revised` |
| `agent_exited` | ON／OFF | `draft_done` |
| `gate_ran` | ON | `gate_ran`（OFF 的一律丟掉，第二道網） |
| `feedback_ready` | — | 不轉（它的位元組數在下一個 `attempt_started` 上，隨 `draft_done` 帶出） |
| `run_ended` | ON | `verdict` ＋（有收據時）`receipt` |
| `run_ended` | OFF | `verdict`（`accepted: null`） |
| 旁註 `postaudit`（`twin.sidecar/1`，**不是** lifecycle） | OFF | `postaudit`（三旗標；只在綁得上那一跑時） |

`counters` 不在這張表上：它不是任何一筆輸入轉出來的，是 `Tally` 依**已經寫出去的**
電視事件數的（`serve_twin._write` 在每一筆 `verdict`／`postaudit` 之後插一筆）。

### `task_kind`：反事實題庫格 vs 分身的自主任務（2026-09-24）

電視上要分得出「這一格是反事實題庫（有閘門、有 OFF 臂）」還是「觀眾分身自己決定的
實務任務（沒有客觀標準、只有 ON 一臂）」。來源是 `run_started.caller.task_kind`
——**呼叫端的標籤**（`run_twin.py` 寫 `"code"`、`twinagent.py` 寫 `"practical"`），
Vacant 本體（`vrun/*`）不為展場加欄位，`caller` 本來就是呼叫端的標籤。

* `task_opened.task_kind` ＝ `caller.task_kind` **原樣**；caller 沒帶就**不寫這個欄位**
  （不替舊錄影猜一個值）。電視與 `tv_contract` 把缺席讀成 `"code"`（相容舊錄影）。
* `practical` 那一格的 `task_id` ＝ `twin_id`（`caller.cell_id`），電視用它對
  twinlink 的 `people[].twin_id`（`screen_contract.join_live_events_on`）。
  **事件流裡沒有他的決定與名字**——那些只在名冊上，撤回就讀不到。

## 誠實邊界（改碼時保留）

1. **`working` 是「這一通經過了中介」，不是「它正在想什麼」。** 它只帶通數，
   不帶內容（lifecycle 誠實邊界 3：事件流不帶 request／response body）。
   而且通數是**下界**：proxy 在回應送完之後才記一通，被 `-9` 砍掉那一刻在途的
   請求不會有 `working`（lifecycle 誠實邊界 6）。`calls_so_far` 不准讀成總數，
   總數以 `verdict` 前那一筆 `draft_done.calls_used` 為準。
2. **電視現在要等 `verdict` 到了才演那一格**（`world3/index.html` 的
   `liveAssemble` 只組「已經有 verdict 的格」）。`working` 讓電視**有資料**在
   114 秒裡動起來，但畫面動不動是電視那一側（A 線）的事；這裡保證的是
   「資料在發生的當下就在檔案裡」。
3. **OFF 臂的事後稽核（`postaudit`）來自分身自己的旁註，不是 Vacant。**
   那是 `run_twin.postaudit_off` 在一跑結束後另外量的，Vacant 當場沒做這件事，
   lifecycle 裡沒有它、也不准進去（2026-09-24 人類裁決「分身側自己記一份補回」）。
   `Folder.feed` 認兩個 schema：`vacant.lifecycle/1` 與 `twin.sidecar/1`（`sidecar.py`），
   其餘一律 `SchemaMismatch`。旁註的 `postaudit` **只在綁得上**時才轉：
   那一跑這一支親眼看過 `run_started`＋`run_ended`、是 OFF、不是 `infra_void`、
   `ws_end_sha256` 與 `cell_id` 都對得上。綁不上就不發，理由記在 `dropped`
   （**不猜**）。它不是從 run 目錄推的：旁註是分身在量的那一刻自己寫的。
4. **證據等級照樣是推的**（`pack.evidence_level`）：`run_ended.requests_seen == 0`
   一律 `L-none`，`caller.declared_evidence` 蓋不過去。開題那一刻還推不出來，
   `task_opened.evidence` 寫 `null`（不寫宣告值）。
5. `caller` 是呼叫端的標籤（`run_twin.py` 塞的），Vacant 沒有驗過它。
6. **一跑死在半路（沒有 `run_ended`）就沒有 `verdict`。** 重播端在播之前先整格
   驗過、過不了就不播（`serve_twin` 的 D2）；但**現場真跑**沒辦法預先驗——
   那一格會一直開著。這一支不替它編一個裁決（那是捏造），電視要自己處理逾時。
7. 重播的 `mode` 由呼叫端傳（`Folder(mode=...)`）。這一支不猜：同一份 lifecycle
   餵進來，`mode` 是什麼就寫什麼。**畫面上標不標「重播」，取決於呼叫端有沒有說實話**
   ——所以 `serve_twin` 的重播路徑把 `"replay"` 寫死，不提供參數改它。

用法：
    # 真跑的同時開另一個終端（或背景）：
    python3 ops/exhibit/twin/run_twin.py --out runs/twin_live --events runs/twin_live/lifecycle.jsonl -- …
    python3 ops/exhibit/twin/live_events.py --in runs/twin_live/lifecycle.jsonl \\
        --out runs/twin_live/events.jsonl --verify-url '/r/{cell}' --follow
    # 電視：world3/index.html?live=<events.jsonl 的網址>&poll=2000
    # 展場正式的路是 serve_twin.py（--recording 重播錄影、--live tail 真跑），不必另起這一支。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
from typing import Any

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import pack as packlib  # noqa: E402
from ops.exhibit.twin import sidecar as sidecarlib  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

#: lifecycle 的 `arm`（launcher 的名字）→ 電視的 `arm`。
ARM_MAP = {"RUN-ON": tv.ARM_ON, "RUN-OFF": tv.ARM_OFF}


class SchemaMismatch(ValueError):
    """契約版號對不上。**不准猜著轉**：換版就是語意可能變了。"""


#: `Folder.feed` 認得的 schema：Vacant 當場觀察到的、以及分身自己的旁註。
SCHEMAS = (lifecycle.SCHEMA, sidecarlib.SCHEMA)


class Folder:
    """一行 lifecycle 進、零到多行電視事件出。有狀態（記得每一跑到哪了）。

    `feed()` 是純函式式的介面：同樣的輸入序列一定得到同樣的輸出（除了 `ts`
    的防撞位移，那也是輸入決定的）。
    """

    def __init__(self, *, verify_url: str, mode: str = tv.MODE_LIVE) -> None:
        if mode not in tv.MODES:
            raise ValueError(f"mode 只能是 {tv.MODES}，拿到 {mode!r}")
        self.verify_url = verify_url
        self.mode = mode
        self.runs: dict[str, dict[str, Any]] = {}
        #: 電視的去重鍵含 `ts`，而同一毫秒發兩筆同 type 是會發生的 ⇒ 全域單調。
        self._last_ms = 0
        #: 每一跑經過中介的通數（`working.calls_so_far` 的來源）。
        self.calls: dict[str, int] = {}
        #: 綁不上、所以沒轉的旁註（誠實邊界 3）。呼叫端可以拿去 /state 講明。
        self.dropped: list[str] = []

    def floor(self, ms: int) -> None:
        """之後發的 `ts` 一定晚於 `ms`。同一個輸出檔裡混了兩個來源（重播＋現場）時，
        呼叫端用它保證整個檔的 `ts` 單調（`tv_contract` 規則 7）。"""
        self._last_ms = max(self._last_ms, int(ms))

    @property
    def last_ms(self) -> int:
        return self._last_ms

    def _ts(self, ms: int) -> str:
        ms = max(int(ms), self._last_ms + 1)
        self._last_ms = ms
        return tv.iso(ms)

    def feed(self, ev: dict) -> list[dict]:
        if ev.get("schema") == sidecarlib.SCHEMA:
            return self._sidecar(ev)
        if ev.get("schema") != lifecycle.SCHEMA:
            raise SchemaMismatch(
                f"版號是 {ev.get('schema')!r}，這一支只認 {SCHEMAS}。"
                "換版要先改這一支（和它的測試），不准猜著轉。")
        t = ev["type"]
        rid = ev["run_id"]
        if t == "run_started":
            caller = ev.get("caller") or {}
            self.runs[rid] = {
                "arm": ARM_MAP.get(ev["arm"], ev["arm"]),
                "cell_id": caller.get("cell_id") or ev["task_id"],
                "resident": caller.get("resident"),
                "prompt": caller.get("prompt") or "",
                "stratum": caller.get("stratum"),
                "declared_evidence": caller.get("declared_evidence") or "",
                # 呼叫端的標籤，原樣轉出去；沒帶就是 None（不猜，見模組 docstring）。
                "task_kind": caller.get("task_kind"),
                "retry": ev.get("retry") or "none",
                "feedback": {},          # attempt → (bytes, delivery)
            }
        st = self.runs.get(rid)
        if st is None:
            return []                    # 沒看到開頭的一跑（檔案從中間開始讀）⇒ 不猜
        out: list[dict] = []
        ts_ms = ev["ts_ms"]

        def emit(kind: str, **kw) -> None:
            out.append({"type": kind, "ts": self._ts(ts_ms),
                        "task_id": st["cell_id"], "mode": self.mode, **kw})

        on = st["arm"] == tv.ARM_ON
        if t == "run_started":
            if on:
                kind = ({"task_kind": st["task_kind"]}
                        if st["task_kind"] is not None else {})
                emit("task_opened", prompt=st["prompt"],
                     prompt_sha256=_sha(st["prompt"]),
                     # 誠實邊界 4：開題那一刻量不到，寫 null 不寫宣告值。
                     evidence=None,
                     evidence_note="跑完才推得出來（要看這一跑實際經過中介幾通）",
                     stratum=st["stratum"], **kind)
                emit("routed", worker=st["resident"], basis="random",
                     basis_note=(tv.PRACTICAL_BASIS_NOTE
                                 if st["task_kind"] == tv.KIND_PRACTICAL else
                                 "`vacant run` 沒有路由層：誰做這一格是人指定的，"
                                 "不是信譽決定的"))
        elif t == "model_call":
            n = self.calls.get(rid, 0) + 1
            self.calls[rid] = n
            # 誠實邊界 1：只帶「又一通經過了中介」與通數，不帶內容。
            emit("working", arm=st["arm"], worker=st["resident"],
                 attempt=ev.get("attempt"), calls_so_far=n)
        elif t == "attempt_started":
            n = ev["attempt"]
            st["feedback"][n] = (ev.get("feedback_in_prompt_bytes"),
                                 ev.get("feedback_delivery"))
            if on and n > 1:
                # 下一次嘗試**真的開始了** ⇒ 上一次沒過而且還有額度。
                # ⚠ reviser ＝ **同一個 worker**：Vacant 的重改是同一個 agent
                #   帶著自己的失敗原文再跑一次，不是評審推翻之後換人重寫。
                emit("revised", arm=tv.ARM_ON, reviser=st["resident"],
                     transition=tv.TRANSITION.get(st["retry"], st["retry"]),
                     retry_arm=st["retry"], attempt=n, of=None)
        elif t == "agent_exited":
            n = ev["attempt"]
            timed_out = bool(ev.get("timed_out"))
            if on:
                fb_bytes, fb_via = st["feedback"].get(n, (None, None))
                emit("draft_done", arm=tv.ARM_ON, worker=st["resident"],
                     calls_used=int(ev.get("requests_seen") or 0),
                     attempt=n, of=None,
                     feedback_bytes=fb_bytes, feedback_delivery=fb_via,
                     feedback_note=tv.FEEDBACK_NOTE.get(fb_via or "", ""),
                     # ⚠ **被牆鐘上限砍掉**與**自己跑完但沒過**是兩個故事，
                     #   而兩者的 stop_reason 都是 visible_fail。
                     timed_out=timed_out,
                     timed_out_note=("這一次是跑到牆鐘上限被砍掉的：交出去驗收的是它當下"
                                     "寫到一半的工作區。「沒過」有一部分是我們沒等它。"
                                     if timed_out else ""),
                     agent_wall_s=ev.get("agent_wall_s"))
            else:
                emit("draft_done", arm=tv.ARM_OFF, worker=st["resident"],
                     calls_used=int(ev.get("requests_seen") or 0),
                     attempt=1, of=1, feedback_bytes=0,
                     timed_out=timed_out,
                     timed_out_note=("這一臂也是跑到牆鐘上限被砍掉的：交出去的是它"
                                     "寫到一半的工作區。" if timed_out else ""),
                     note="沒有 Vacant 的那一臂：一次 spawn、沒有閘門、沒有回饋、沒有第二次。")
        elif t == "gate_ran":
            # lifecycle 的 validate 已經擋掉 OFF 的 gate_ran；這裡再擋一次（兩道網）。
            if on:
                emit("gate_ran", arm=tv.ARM_ON, passed=bool(ev.get("passed")),
                     n_tests=ev.get("n_tests"), failed_case=ev.get("failed_case"),
                     attempt=ev["attempt"], of=None)
        elif t == "run_ended":
            st.update(ended=True, ws_end=ev.get("ws_end_sha256"),
                      infra_void=ev.get("infra_void"))
            self._ended(st, ev, emit)
        return out

    def _sidecar(self, ev: dict) -> list[dict]:
        """分身的旁註 → 電視的 `postaudit`。**綁不上就不發**（誠實邊界 3）。"""
        t = ev.get("type")
        rid = ev.get("run_id")
        why = None
        st = self.runs.get(rid)
        if t != "postaudit":
            why = f"不認得的旁註 type {t!r}"
        elif (ev.get("when"), ev.get("is_verdict"), ev.get("signed")) != \
                (tv.WHEN_AFTER, False, False):
            # 自稱裁決（或沒說自己是事後）的旁註**不轉**——不是替它改正旗標再播。
            why = "postaudit 的三個旗標不對（when／is_verdict／signed），不當成事後稽核播"
        elif st is None:
            why = f"postaudit 綁的那一跑 {rid} 這一支沒看過 run_started"
        elif st["arm"] != tv.ARM_OFF:
            why = f"postaudit 綁的那一跑 {rid} 不是 OFF 臂"
        elif not st.get("ended"):
            why = f"postaudit 綁的那一跑 {rid} 還沒有 run_ended（事後稽核不能早於那一跑結束）"
        elif st.get("infra_void"):
            why = f"postaudit 綁的那一跑 {rid} 是 infra_void（沒跑成就沒有東西可量）"
        elif ev.get("ws_end_sha256") != st.get("ws_end"):
            why = f"postaudit 的 ws_end_sha256 與那一跑 {rid} 不同（量的不是那一棵樹）"
        elif ev.get("cell_id") != st["cell_id"]:
            why = f"postaudit 的 cell_id 與那一跑 {rid} 的格子不同"
        if why:
            self.dropped.append(why)
            return []
        return [{"type": "postaudit", "ts": self._ts(ev["ts_ms"]),
                 "task_id": st["cell_id"], "mode": self.mode, "arm": tv.ARM_OFF,
                 # ⚠ 三個旗標**寫死**（上面已確認旁註自己也這樣說）：電視這一側
                 #   不從任何輸入抄這三個值，改碼的人也就沒有地方把它改成裁決。
                 "when": tv.WHEN_AFTER, "is_verdict": False, "signed": False,
                 "all_pass": bool(ev.get("all_pass")),
                 "passed": ev.get("passed"), "n_tests": ev.get("total"),
                 "failed_case": ev.get("failed_case"),
                 "ruler": ev.get("ruler"), "note": ev.get("note"),
                 "ws_end_sha256": ev.get("ws_end_sha256")}]

    def _ended(self, st: dict, ev: dict, emit) -> None:
        on = st["arm"] == tv.ARM_ON
        level = packlib.evidence_level(
            requests_seen=int(ev.get("requests_seen") or 0),
            declared=st["declared_evidence"])
        if ev.get("infra_void"):
            # 鐵律 3：沒量到不長成數字。但**一定要發 verdict**——開了題卻沒有
            # verdict，電視的佇列會卡死在這一格（`tv_contract` 規則 6）。
            emit("verdict", arm=st["arm"], accepted=None, meets_demand=None,
                 blocked_by=None, stop_reason="infra_void",
                 infra_void=str(ev["infra_void"]),
                 note="這一臂的基建壞了 ⇒ 沒有量到任何東西。不是「沒過」，是「沒跑成」。",
                 attempts_used=ev.get("attempts_used"),
                 retry=st["retry"] if on else "none", evidence=level)
            return
        stop = ev.get("stop_reason") or ""
        if not on:
            emit("verdict", arm=tv.ARM_OFF, accepted=None, meets_demand=None,
                 blocked_by=None, stop_reason=stop or "ungated",
                 accepted_note=packlib.OFF_ACCEPTED_NOTE,
                 has_receipt=bool(ev.get("has_receipt")),
                 has_receipt_note=packlib.OFF_HAS_RECEIPT_NOTE,
                 attempts_used=ev.get("attempts_used"), retry="none",
                 evidence=level)
            return
        accepted = ev.get("accepted")       # 三值，不做 bool()
        # 分身的自主任務：`accepted=null` 的意思是「這類任務沒有客觀標準、不判」，
        # 不是「沒過」。那句話跟著事件走，電視不用自己猜（`tv_contract` 規則 11）。
        pnote = ({"accepted_note": tv.PRACTICAL_ACCEPTED_NOTE}
                 if st["task_kind"] == tv.KIND_PRACTICAL else {})
        emit("verdict", arm=tv.ARM_ON, accepted=accepted, **pnote,
             # meets_demand 要隱藏測資才答得出來，而隱藏測資不進展件 ⇒ 恆 null
             meets_demand=None,
             blocked_by=tv.BLOCKED_BY.get(stop, "gate" if accepted is False else None),
             stop_reason=stop, attempts_used=ev.get("attempts_used"),
             retry=st["retry"], evidence=level,
             evidence_note=packlib.EVIDENCE_TEXT.get(level, ""))
        if ev.get("has_receipt"):
            head = ev.get("verdict_hash") or ""
            emit("receipt", arm=tv.ARM_ON, sha256=head, chain_head=head,
                 verify_url=tv.cell_verify_url(self.verify_url, st["cell_id"]),
                 # ⚠ 收據 hash 與題面 hash 是兩個東西，各帶一份。
                 prompt_sha256=_sha(st["prompt"]),
                 verdict_sha256=ev.get("verdict_sha256"),
                 ws_end_sha256=ev.get("ws_end_sha256"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fold(events: list[dict], *, verify_url: str, mode: str = tv.MODE_LIVE) -> list[dict]:
    """一次轉完（測試、離線檢查與重播預演用）。不發 `counters`（那是播放端的事）。"""
    f = Folder(verify_url=verify_url, mode=mode)
    out: list[dict] = []
    for ev in events:
        out.extend(f.feed(ev))
    return out


def read_recording(path) -> tuple[list[dict], list[dict]]:
    """一份錄影 → `(lifecycle 事件, 旁註)`。旁註檔不在＝空清單（舊錄影）。"""
    path = pathlib.Path(path)
    return lifecycle.read(path), sidecarlib.read(sidecarlib.sidecar_path(path))


class Tally:
    """`counters` 的來源：**已經寫出去的**電視事件逐筆餵進來，數到哪裡算到哪裡。

    - 以 `task_id`（＝格子）為鍵：同一格播第二次**取代**上一次，不重複算。
      所以「播過的格子」是**不同格子**的數目，不是播放次數。
    - 一個 `Tally` 只數一種 `mode`（`serve_twin` 重播一個、現場一個）：
      把錄影與現場加在一起，就是把「以前跑過的」與「此刻在跑的」講成同一批。
    - OFF 的 `verdict` 再來一次 ⇒ 那一格的舊 `postaudit` 作廢
      （新的一跑有沒有事後稽核，要等它自己的旁註）。

    ⚠ 真實累計值，不是估計；**沒量到的欄位不發**：沒播過 ON 的格就沒有
    `total`，沒播過 OFF 就沒有 `off_*`，沒播過 postaudit 就沒有
    `off_postaudited`／`off_postaudit_not_all_pass`（0/0 會被讀成「全過」）。
    `audited`／`on_leaked`／`off_leaked` 永遠不發（`tv.COUNTERS_NEVER`）。
    `blocked`＝ON `accepted` 為 false、`delivered`＝為 true；`null`（沒量／基建壞）
    兩邊都不算，但算進 `total`。
    """

    OFF_NOTE = ("OFF 臂沒有裁決可以計數（它不驗收）。off_postaudit 那兩欄是分身**事後**"
                "用同一份可見驗收量出來的，不是那一跑當場的判定。")
    SCOPE_NOTE = ("只數這台機器**已經播出去**的格子（同一格播兩次算一格），"
                  "重播與現場分開數。")

    def __init__(self) -> None:
        self.cells: dict[str, dict] = {}

    def feed(self, e: dict) -> bool:
        """回 `True`＝數字變了（呼叫端該發一筆 `counters`）。"""
        t, cid, arm = e.get("type"), e.get("task_id"), e.get("arm")
        if t == "verdict" and arm == tv.ARM_ON:
            self.cells.setdefault(cid, {})["on"] = {
                "accepted": e.get("accepted"), "evidence": e.get("evidence")}
            return True
        if t == "verdict" and arm == tv.ARM_OFF:
            slot = self.cells.setdefault(cid, {})
            slot["off"] = {"void": e.get("stop_reason") == "infra_void",
                           "has_receipt": bool(e.get("has_receipt"))}
            slot.pop("pa", None)
            return True
        if t == "postaudit" and arm == tv.ARM_OFF:
            self.cells.setdefault(cid, {})["pa"] = {"all_pass": bool(e.get("all_pass"))}
            return True
        return False

    def event(self, *, ts: str, mode: str) -> dict:
        ons = [s["on"] for s in self.cells.values() if "on" in s]
        offs = [s["off"] for s in self.cells.values()
                if "off" in s and not s["off"]["void"]]
        pas = [s["pa"] for s in self.cells.values() if "pa" in s]
        ev: dict = {"type": "counters", "ts": ts, "task_id": "-", "mode": mode,
                    "scope_note": self.SCOPE_NOTE}
        if ons:
            levels: dict[str, int] = {}
            for o in ons:
                if o["evidence"]:
                    levels[o["evidence"]] = levels.get(o["evidence"], 0) + 1
            ev.update({
                "total": len(ons),
                "blocked": sum(1 for o in ons if o["accepted"] is False),
                "delivered": sum(1 for o in ons if o["accepted"] is True),
                "evidence_counts": dict(sorted(levels.items())),
            })
        if offs:
            ev.update({"off_ran": len(offs),
                       "off_with_receipt": sum(1 for o in offs if o["has_receipt"]),
                       "off_counters_note": self.OFF_NOTE})
        if pas:
            ev.update({"off_postaudited": len(pas),
                       "off_postaudit_not_all_pass": sum(
                           1 for p in pas if not p["all_pass"])})
        return ev


def with_counters(evs: list[dict], tallies: dict[str, Tally]) -> list[dict]:
    """每一筆讓數字變了的事件之後，緊接著插一筆 `counters`（`ts` 與它相同）。

    `ts` 取觸發那一筆的：事件檔的 `ts` 單調不減照樣成立，而去重鍵含 `type`，
    與觸發那一筆不會撞；觸發事件的 `ts` 在整個檔裡本來就唯一（`Folder._ts`），
    所以兩筆 `counters` 也不會撞。`tallies` 以 `mode` 為鍵，沒有的 mode 不數。
    """
    out: list[dict] = []
    for e in evs:
        out.append(e)
        tally = tallies.get(e.get("mode"))
        if tally is not None and tally.feed(e):
            out.append(tally.event(ts=e["ts"], mode=e["mode"]))
    return out


class Tail:
    """tail 一個還在長的 lifecycle 檔。每次 `poll()` 回這一輪新接到的**完整**行。

    只吃到**最後一個換行**為止：另一個行程寫到一半的那一行留到下一輪
    （`lifecycle.read` 的同一條規則）。

    `start_at_end=True`：從檔尾開始讀（`serve_twin --live` 用）。檔案裡**已經有的**
    東西不是「正在發生」——把它當 live 播出去等於把錄影講成現場。
    代價：開機那一刻正在跑的那一跑，`Folder` 看不到它的 `run_started`，整跑都不轉
    （`Folder.feed` 的「不猜」規則）。
    """

    def __init__(self, src: pathlib.Path, *, start_at_end: bool = False) -> None:
        self.src = pathlib.Path(src)
        self.pos = 0
        self.buf = b""
        if start_at_end and self.src.exists():
            self.pos = self.src.stat().st_size
        #: 這一支親眼看到 `run_started`、還沒看到 `run_ended` 的跑。
        self.open_runs: set[str] = set()
        self.last_line_mono: float | None = None
        self.n_lines = 0

    def poll(self) -> list[dict]:
        if not self.src.exists():
            return []
        size = self.src.stat().st_size
        if size < self.pos:
            # 檔案被截短／換了一個 ⇒ 從頭開始（不然永遠讀不到新東西）。
            self.pos, self.buf = 0, b""
        with self.src.open("rb") as fh:
            fh.seek(self.pos)
            chunk = fh.read()
        if not chunk:
            return []
        self.pos += len(chunk)
        self.buf += chunk
        *lines, self.buf = self.buf.split(b"\n")
        out = []
        for ln in lines:
            if not ln.strip():
                continue
            ev = json.loads(ln)
            out.append(ev)
            if ev.get("type") == "run_started":
                self.open_runs.add(ev.get("run_id"))
            elif ev.get("type") == "run_ended":
                self.open_runs.discard(ev.get("run_id"))
        if out:
            self.last_line_mono = time.monotonic()
            self.n_lines += len(out)
        return out


def follow(src: pathlib.Path, out: pathlib.Path, *, verify_url: str,
           mode: str = tv.MODE_LIVE, interval: float = 0.5,
           idle_exit_s: float | None = None, sleep=time.sleep) -> int:
    """tail `src`，每接到一行完整的 lifecycle 就把轉出來的事件追加到 `out`。

    `idle_exit_s` 給了 ⇒ 那麼久沒有新行就結束（測試與批次用；展場不給，一直跑）。
    """
    f = Folder(verify_url=verify_url, mode=mode)
    tail = Tail(src)
    # 分身的旁註（postaudit）在旁邊的 `X.sidecar.jsonl`；先 lifecycle 後旁註，
    # 同一輪裡 OFF 的 run_ended 才會在它的 postaudit 之前進 Folder。
    side = Tail(sidecarlib.sidecar_path(src))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.touch()
    idle, n_out = 0.0, 0
    while True:
        lines = tail.poll() + side.poll()
        new: list[dict] = []
        for ev in lines:
            new.extend(f.feed(ev))
        if new:
            with out.open("a", encoding="utf-8") as oh:
                for e in new:
                    oh.write(json.dumps(e, ensure_ascii=False) + "\n")
            n_out += len(new)
        idle = 0.0 if lines else idle + interval
        if idle_exit_s is not None and idle >= idle_exit_s:
            return n_out
        sleep(interval)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="lifecycle 事件流 → 電視的 world event")
    ap.add_argument("--in", dest="src", required=True, help="vacant run --events 寫的那個檔")
    ap.add_argument("--out", required=True, help="電視輪詢的 events.jsonl")
    ap.add_argument("--verify-url", default="/r/{cell}",
                    help="收據頁網址；`{cell}` 換成 cell_id（預設 serve_twin 的 /r/<cell>）")
    ap.add_argument("--mode", choices=tv.MODES, default=tv.MODE_LIVE,
                    help="live＝正在真跑；replay＝重播錄影（電視會在畫面上標「重播」）")
    ap.add_argument("--follow", action="store_true", help="一直 tail（展場用）")
    ap.add_argument("--interval", type=float, default=0.5)
    a = ap.parse_args(argv)
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    if a.follow:
        return 0 if follow(src, out, verify_url=a.verify_url, mode=a.mode,
                           interval=a.interval) >= 0 else 1
    lc, rows = read_recording(src)
    evs = fold(sidecarlib.merge(lc, rows), verify_url=a.verify_url, mode=a.mode)
    bad = tv.validate(evs)
    out.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs),
                   encoding="utf-8")
    print(f"{len(evs)} 筆 → {out}" + (f"；契約問題 {len(bad)} 條" if bad else ""),
          file=sys.stderr)
    for b in bad:
        print("  " + b, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
