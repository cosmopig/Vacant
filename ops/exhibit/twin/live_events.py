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
3. **OFF 臂的事後稽核（`postaudit`）不從這裡出，電視也就看不到它。**
   那是 `run_twin.postaudit_off` 在一跑結束後另外量的，Vacant 當場沒做這件事，
   lifecycle 裡沒有它。事後推導那一條刪掉之後，這個數字在電視上**消失了**——
   要它回來得先進 lifecycle 契約，不准在這裡另開一條推導。
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
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

#: lifecycle 的 `arm`（launcher 的名字）→ 電視的 `arm`。
ARM_MAP = {"RUN-ON": tv.ARM_ON, "RUN-OFF": tv.ARM_OFF}


class SchemaMismatch(ValueError):
    """契約版號對不上。**不准猜著轉**：換版就是語意可能變了。"""


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
        if ev.get("schema") != lifecycle.SCHEMA:
            raise SchemaMismatch(
                f"lifecycle 版號是 {ev.get('schema')!r}，這一支只認 {lifecycle.SCHEMA}。"
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
                emit("task_opened", prompt=st["prompt"],
                     prompt_sha256=_sha(st["prompt"]),
                     # 誠實邊界 4：開題那一刻量不到，寫 null 不寫宣告值。
                     evidence=None,
                     evidence_note="跑完才推得出來（要看這一跑實際經過中介幾通）",
                     stratum=st["stratum"])
                emit("routed", worker=st["resident"], basis="random",
                     basis_note="`vacant run` 沒有路由層：誰做這一格是人指定的，"
                                "不是信譽決定的")
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
            self._ended(st, ev, emit)
        return out

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
        emit("verdict", arm=tv.ARM_ON, accepted=accepted,
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
    """一次轉完（測試、離線檢查與重播預演用）。"""
    f = Folder(verify_url=verify_url, mode=mode)
    out: list[dict] = []
    for ev in events:
        out.extend(f.feed(ev))
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
    out.parent.mkdir(parents=True, exist_ok=True)
    out.touch()
    idle, n_out = 0.0, 0
    while True:
        lines = tail.poll()
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
    evs = fold(lifecycle.read(src), verify_url=a.verify_url, mode=a.mode)
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
