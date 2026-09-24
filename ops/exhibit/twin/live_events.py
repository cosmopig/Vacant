"""twin/live_events — `vacant.lifecycle/1` 事件流 → 電視吃的 world event（**跑的當下**）。

## 這支在架構裡承重什麼

`to_events.py` 是**事後**那一條：等一跑結束，讀 run 目錄，推回一串事件。
這一支是**當下**那一條：`vacant run --events <檔>` 每觀察到一件事就寫一行，
這裡一行一行接住、轉成 `LIVE_INTERFACE.md` 的 type，追加給電視。

```
 vacant run（pi／OpenCode／…）──lifecycle.jsonl──▶ 這一支 ──events.jsonl──▶ 電視 ?live=
      觀察到的人當場寫               只認契約            LIVE_INTERFACE.md
```

**分身只認 `vacant_network/vrun/lifecycle.py` 那一份契約，不讀 run 目錄的內臟。**
於是 Vacant 怎麼迭代（落盤檔名、`attempts` 陣列的形狀、收據欄位）都碰不到這裡；
只有契約版號（`SCHEMA`）變了才要動這一支——而那時 `fold()` 會大聲拒絕，
不會安靜地演錯。

## 兩條線必須講同一件事

同一跑，「當下轉的」與「事後推的」在**語意**上必須相同。可執行證明＝
`tests/test_twin_live_events.py::test_live_matches_posthoc_for_the_same_runs`：
用 `run_twin.py --fixture --events` 真跑一批，兩條線各自產出，逐欄比。
刻意不比的欄位與理由（寫死在測試的 `LIVE_ONLY_DIFFS`）：

| 欄位 | 事後 | 當下 | 為什麼不一樣是對的 |
|---|---|---|---|
| `ts` | 人造間隔 | 真的牆鐘 | 當下那條的時間就是發生的時間 |
| `of` | 實際用了幾次 | `null` | **跑到一半不知道總數**（lifecycle 誠實邊界 4）。電視 `of` 缺席時會用 `draft_done` 的筆數 |
| `task_opened.evidence` | 推出來的等級 | `null` | 證據等級要 `requests_seen` 才推得出來，開題那一刻還沒有。推出來的值放在 `verdict.evidence` |
| `postaudit` | 有 | 沒有 | 事後稽核不是 Vacant 做的事，不在 lifecycle 裡（見誠實邊界 3） |

## 誠實邊界（改碼時保留）

1. **`model_call` 目前不轉成任何電視事件。** `LIVE_INTERFACE.md` 沒有「正在寫」
   這種 type；自己發一個電視不認得的 type，`to_events.validate` 會擋，而且那等於
   在契約外加層。要讓畫面在一題 114 秒裡動起來，得先在電視那一側加 type
   （`vacant_hm/world3`）。本支把次數累計在 `Folder.calls` 讓那一天可以直接接。
2. **電視現在要等 `verdict` 到了才演那一格**（`world3/index.html` 的
   `liveAssemble` 只組「已經有 verdict 的格」）。所以即使這一支逐筆吐，
   **畫面上仍然是一格一格跳，不是過程中逐拍動**。這是電視那一側的事，
   不是這一支能修的；這裡保證的是「資料在發生的當下就在檔案裡」。
3. **OFF 臂的事後稽核（`postaudit`）不從這裡出。** 那是 `run_twin.postaudit_off`
   在一跑結束後另外量的，Vacant 當場沒做這件事，lifecycle 裡也就不會有它。
4. **證據等級照樣是推的**（`pack.evidence_level`）：`run_ended.requests_seen == 0`
   一律 `L-none`，`caller.declared_evidence` 蓋不過去。
5. `caller` 是呼叫端的標籤（`run_twin.py` 塞的），Vacant 沒有驗過它。

用法：
    # 真跑的同時開另一個終端（或背景）：
    python3 ops/exhibit/twin/run_twin.py --out runs/twin_live --events runs/twin_live/lifecycle.jsonl -- …
    python3 ops/exhibit/twin/live_events.py --in runs/twin_live/lifecycle.jsonl \\
        --out runs/twin_live/events.jsonl --verify-url '/r/{cell}' --follow
    # 電視：world3/index.html?live=<events.jsonl 的網址>&poll=2000
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
from ops.exhibit.twin import to_events as te  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

#: lifecycle 的 `arm`（launcher 的名字）→ 電視的 `arm`。
ARM_MAP = {"RUN-ON": te.ARM_ON, "RUN-OFF": te.ARM_OFF}


class SchemaMismatch(ValueError):
    """契約版號對不上。**不准猜著轉**：換版就是語意可能變了。"""


class Folder:
    """一行 lifecycle 進、零到多行電視事件出。有狀態（記得每一跑到哪了）。

    `feed()` 是純函式式的介面：同樣的輸入序列一定得到同樣的輸出（除了 `ts`
    的防撞位移，那也是輸入決定的）。
    """

    def __init__(self, *, verify_url: str) -> None:
        self.verify_url = verify_url
        self.runs: dict[str, dict[str, Any]] = {}
        #: 電視的去重鍵含 `ts`，而同一毫秒發兩筆同 type 是會發生的 ⇒ 全域單調。
        self._last_ms = 0
        #: 誠實邊界 1：還沒有電視事件可以承載，但次數留著。
        self.calls: dict[str, int] = {}

    def _ts(self, ms: int) -> str:
        ms = max(int(ms), self._last_ms + 1)
        self._last_ms = ms
        return te.iso(ms)

    def feed(self, ev: dict) -> list[dict]:
        if ev.get("schema") != lifecycle.SCHEMA:
            raise SchemaMismatch(
                f"lifecycle 版號是 {ev.get('schema')!r}，這一支只認 {lifecycle.SCHEMA}。"
                "換版要先改這一支（和它的對照測試），不准猜著轉。")
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
                "last_gate_sha": None,
            }
        st = self.runs.get(rid)
        if st is None:
            return []                    # 沒看到開頭的一跑（檔案從中間開始讀）⇒ 不猜
        out: list[dict] = []
        ts_ms = ev["ts_ms"]

        def emit(kind: str, **kw) -> None:
            out.append({"type": kind, "ts": self._ts(ts_ms),
                        "task_id": st["cell_id"], **kw})

        on = st["arm"] == te.ARM_ON
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
            self.calls[rid] = self.calls.get(rid, 0) + 1
        elif t == "attempt_started":
            n = ev["attempt"]
            st["feedback"][n] = (ev.get("feedback_in_prompt_bytes"),
                                 ev.get("feedback_delivery"))
            if on and n > 1:
                # 下一次嘗試**真的開始了** ⇒ 上一次沒過而且還有額度。
                emit("revised", arm=te.ARM_ON, reviser=st["resident"],
                     transition=te.TRANSITION.get(st["retry"], st["retry"]),
                     retry_arm=st["retry"], attempt=n, of=None)
        elif t == "agent_exited":
            n = ev["attempt"]
            timed_out = bool(ev.get("timed_out"))
            if on:
                fb_bytes, fb_via = st["feedback"].get(n, (None, None))
                emit("draft_done", arm=te.ARM_ON, worker=st["resident"],
                     calls_used=int(ev.get("requests_seen") or 0),
                     attempt=n, of=None,
                     feedback_bytes=fb_bytes, feedback_delivery=fb_via,
                     feedback_note=te.FEEDBACK_NOTE.get(fb_via or "", ""),
                     timed_out=timed_out,
                     timed_out_note=("這一次是跑到牆鐘上限被砍掉的：交出去驗收的是它當下"
                                     "寫到一半的工作區。「沒過」有一部分是我們沒等它。"
                                     if timed_out else ""),
                     agent_wall_s=ev.get("agent_wall_s"))
            else:
                emit("draft_done", arm=te.ARM_OFF, worker=st["resident"],
                     calls_used=int(ev.get("requests_seen") or 0),
                     attempt=1, of=1, feedback_bytes=0,
                     timed_out=timed_out,
                     timed_out_note=("這一臂也是跑到牆鐘上限被砍掉的：事後稽核量到的是"
                                     "它寫到一半的工作區。" if timed_out else ""),
                     note="沒有 Vacant 的那一臂：一次 spawn、沒有閘門、沒有回饋、沒有第二次。")
        elif t == "gate_ran":
            # lifecycle 的 validate 已經擋掉 OFF 的 gate_ran；這裡再擋一次（兩道網）。
            if on:
                emit("gate_ran", arm=te.ARM_ON, passed=bool(ev.get("passed")),
                     n_tests=ev.get("n_tests"), failed_case=ev.get("failed_case"),
                     attempt=ev["attempt"], of=None)
        elif t == "run_ended":
            out.extend(self._ended(st, ev, emit))
        return out

    def _ended(self, st: dict, ev: dict, emit) -> list[dict]:
        on = st["arm"] == te.ARM_ON
        level = packlib.evidence_level(
            requests_seen=int(ev.get("requests_seen") or 0),
            declared=st["declared_evidence"])
        if ev.get("infra_void"):
            # 鐵律 3：沒量到不長成數字。但**一定要發 verdict**——開了題卻沒有
            # verdict，電視的佇列會卡死在這一格（`to_events.validate` 的最後一條）。
            emit("verdict", arm=st["arm"], accepted=None, meets_demand=None,
                 blocked_by=None, stop_reason="infra_void",
                 infra_void=str(ev["infra_void"]),
                 note="這一臂的基建壞了 ⇒ 沒有量到任何東西。不是「沒過」，是「沒跑成」。",
                 attempts_used=ev.get("attempts_used"),
                 retry=st["retry"] if on else "none", evidence=level)
            return []
        stop = ev.get("stop_reason") or ""
        if not on:
            emit("verdict", arm=te.ARM_OFF, accepted=None, meets_demand=None,
                 blocked_by=None, stop_reason=stop or "ungated",
                 accepted_note=packlib.OFF_ACCEPTED_NOTE,
                 has_receipt=bool(ev.get("has_receipt")),
                 has_receipt_note=packlib.OFF_HAS_RECEIPT_NOTE,
                 attempts_used=ev.get("attempts_used"), retry="none",
                 evidence=level)
            return []
        accepted = ev.get("accepted")       # 三值，不做 bool()
        emit("verdict", arm=te.ARM_ON, accepted=accepted, meets_demand=None,
             blocked_by=te.BLOCKED_BY.get(stop, "gate" if accepted is False else None),
             stop_reason=stop, attempts_used=ev.get("attempts_used"),
             retry=st["retry"], evidence=level,
             evidence_note=packlib.EVIDENCE_TEXT.get(level, ""))
        if ev.get("has_receipt"):
            head = ev.get("verdict_hash") or ""
            emit("receipt", arm=te.ARM_ON, sha256=head, chain_head=head,
                 verify_url=te.cell_verify_url(self.verify_url, st["cell_id"]),
                 prompt_sha256=_sha(st["prompt"]),
                 verdict_sha256=ev.get("verdict_sha256"),
                 ws_end_sha256=ev.get("ws_end_sha256"))
        return []


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fold(events: list[dict], *, verify_url: str) -> list[dict]:
    """一次轉完（測試與離線用）。"""
    f = Folder(verify_url=verify_url)
    out: list[dict] = []
    for ev in events:
        out.extend(f.feed(ev))
    return out


def follow(src: pathlib.Path, out: pathlib.Path, *, verify_url: str,
           interval: float = 0.5, idle_exit_s: float | None = None,
           sleep=time.sleep) -> int:
    """tail `src`，每接到一行完整的 lifecycle 就把轉出來的事件追加到 `out`。

    只吃到**最後一個換行**為止：另一個行程寫到一半的那一行留到下一輪
    （`lifecycle.read` 的同一條規則）。`idle_exit_s` 給了 ⇒ 那麼久沒有新行就結束
    （測試與批次用；展場不給，一直跑）。
    """
    f = Folder(verify_url=verify_url)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.touch()
    pos, buf, idle, n_out = 0, b"", 0.0, 0
    while True:
        got = False
        if src.exists():
            with src.open("rb") as fh:
                fh.seek(pos)
                chunk = fh.read()
            if chunk:
                pos += len(chunk)
                buf += chunk
                *lines, buf = buf.split(b"\n")
                new: list[dict] = []
                for ln in lines:
                    if ln.strip():
                        new.extend(f.feed(json.loads(ln)))
                if new:
                    with out.open("a", encoding="utf-8") as oh:
                        for e in new:
                            oh.write(json.dumps(e, ensure_ascii=False) + "\n")
                    n_out += len(new)
                got = bool(lines)
        idle = 0.0 if got else idle + interval
        if idle_exit_s is not None and idle >= idle_exit_s:
            return n_out
        sleep(interval)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="lifecycle 事件流 → 電視的 world event（當下）")
    ap.add_argument("--in", dest="src", required=True, help="vacant run --events 寫的那個檔")
    ap.add_argument("--out", required=True, help="電視輪詢的 events.jsonl")
    ap.add_argument("--verify-url", default="/r/{cell}",
                    help="收據頁網址；`{cell}` 換成 cell_id（預設 serve_twin 的 /r/<cell>）")
    ap.add_argument("--follow", action="store_true", help="一直 tail（展場用）")
    ap.add_argument("--interval", type=float, default=0.5)
    a = ap.parse_args(argv)
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    if a.follow:
        return 0 if follow(src, out, verify_url=a.verify_url,
                           interval=a.interval) >= 0 else 1
    evs = fold(lifecycle.read(src), verify_url=a.verify_url)
    bad = te.validate(evs)
    out.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs),
                   encoding="utf-8")
    print(f"{len(evs)} 筆 → {out}" + (f"；契約問題 {len(bad)} 條" if bad else ""),
          file=sys.stderr)
    for b in bad:
        print("  " + b, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
