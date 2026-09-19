"""twin/to_events — `vacant run` 的 run 目錄 → 人類動物園電視吃的 world event。

## 這支在架構裡承重什麼：**這就是「接好 vacant world」那一條線**

電視（`vacant_hm/world3/index.html`）早就寫好了活模式：`?live=<串流網址>&poll=2000`，
它每隔幾秒抓一次、依 `ts` 去重、把事件組成一筆可播的紀錄。契約寫在
`vacant_hm/world3/docs/LIVE_INTERFACE.md`，而那份文件自己的 §四誠實地寫著：

  > 活模式尚未在真 agent 上跑過——只用 rows_to_events 的重放驗證過格式。
  > `verify_url`：讓觀眾自己重驗收據的頁面還沒做。

兩個缺口都在**生產端**，不在電視端。本支補第一個（真 agent 吐得出事件），
`examples/twin_viewer.html` 補第二個（`verify_url` 指得到的那一頁）。

⇒ 電視一個字都不用改。凍結重放與真跑 agent 吐同一種事件，換資料源不用改電視。

## 對照表（左邊是 `vacant run` 落盤的東西，右邊是 LIVE_INTERFACE.md 的 type）

| 事件 | 從哪來 | 備註 |
|---|---|---|
| `task_opened` | 工作區的 `TASK.md` | `prompt_sha256` ＝ 題面的 sha256 |
| `routed` | 名冊 | `basis` 固定 `"random"`——**這一批沒有信譽路由**，不准寫成有 |
| `draft_done` | `attempts` 陣列 | `calls_used` ＝ 該次嘗試的 `requests_seen` |
| `gate_ran` | `visible_*.json` | 這是 CONFORM 架構的核心，也是展場步 7 的主戲 |
| `verdict` | 鏈上的 `ws_verdict` | **讀簽章覆蓋的那一份**，不讀 run 摘要 |
| `receipt` | 鏈頭 | `verify_url` 指向離線收據頁 |
| `counters` | 整批累計 | 真實累計值，不是估計 |

**沒發生的步驟不發事件**（LIVE_INTERFACE.md 的硬性誠實規則）：這一批沒有評審、
沒有修訂、沒有抽樣稽核，所以 `review_vote`／`revised`／`audited` **一個都不發**，
電視會照實說「這一次沒有走到這一步」。多發一個空事件就是把沒做的事畫出來。

## 誠實邊界

1. `basis` 只有在路由真的由信譽層決定時才准填 `"reputation"`。`vacant run` 沒有
   路由層——一格一個 agent，誰做是人指定的。所以這支**寫死 `"random"`**，
   而且不提供參數改它：一個可以用旗標改成 `"reputation"` 的欄位遲早會被改。
2. `meets_demand` 需要隱藏測資才答得出來，而隱藏測資不准進展件（V/GT 紅線）。
   所以本支**不發** `meets_demand=true`——`verdict` 只帶 `accepted`
   （可見驗收過了沒），`meets_demand` 留成 `null`，電視顯示「—」。
   把 `accepted` 寫成 `meets_demand` 就是把「通過驗收」講成「符合需求」。
3. 事件流本身**沒有簽章**（LIVE_INTERFACE.md §四 已經記了這條）。
   可驗的那一份是收據頁，不是這條串流。電視是展示端不是證據端。

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
EMITTED = ("task_opened", "routed", "draft_done", "gate_ran", "verdict",
           "receipt", "counters")


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def events_for_cell(cell: dict, *, verify_url: str, ts_ms: int) -> list[dict]:
    """一格 → 一串事件。`cell` 是 `pack.pack_cell()` 的輸出。

    `task_id` 用 `cell_id`：電視的去重鍵是 `ts|type|task_id|arm|reviewer`，
    同一題在不同居民手上是**不同的一格**，共用 task_id 會被去重吃掉一格。
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
       prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest())

    # basis 寫死 random：vacant run 沒有路由層，誰做這一格是人指定的（誠實邊界 1）。
    ev("routed", worker=cell["resident"], basis="random")

    ev("draft_done", worker=cell["resident"], calls_used=cell["requests_seen"])

    failed = next((c["case"] for c in cell["visible"]["cases"] if not c["ok"]), None)
    ev("gate_ran", passed=bool(cell["visible"]["all_pass"]),
       n_tests=cell["visible"]["total"], failed_case=failed)

    # 裁決讀**簽章覆蓋的那一份**，不讀 run 摘要。
    accepted = None
    for line in cell["chain"]:
        d = json.loads(line)
        if d["type"] == "ws_verdict":
            accepted = d["payload"].get("accepted")
    ev("verdict", accepted=bool(accepted),
       # meets_demand 要隱藏測資才答得出來，而隱藏測資不進展件 ⇒ 留 null（誠實邊界 2）
       meets_demand=None,
       blocked_by=None if accepted else "gate")

    head = ""
    if cell["chain"]:
        from vacant.logbook import LogEntry
        head = LogEntry.from_json(json.loads(cell["chain"][-1])).hash()
    ev("receipt", sha256=head, chain_head=head, verify_url=verify_url)
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
    evs.append({
        "type": "counters", "ts": iso(ts), "task_id": "-",
        "blocked": pack["refused"], "audited": 0, "total": len(pack["cells"]),
    })
    return evs


def validate(evs: list[dict]) -> list[str]:
    """契約自檢：每個事件都要有必要欄位、type 要在白名單、ts 要單調不減。"""
    bad = []
    last = ""
    for i, e in enumerate(evs):
        for k in REQUIRED:
            if k not in e:
                bad.append(f"第 {i + 1} 個事件缺欄位 {k}")
        if e.get("type") not in EMITTED:
            bad.append(f"第 {i + 1} 個事件的 type 不在白名單：{e.get('type')!r}")
        if e.get("ts", "") < last:
            bad.append(f"第 {i + 1} 個事件的 ts 比前一個早")
        last = e.get("ts", last)
    # 電視的去重鍵：ts|type|task_id|arm|reviewer。撞鍵 ⇒ 那一格會被靜靜吃掉。
    keys = ["%s|%s|%s|%s|%s" % (e.get("ts"), e.get("type"), e.get("task_id"),
                                e.get("arm", ""), e.get("reviewer", "")) for e in evs]
    if len(set(keys)) != len(keys):
        bad.append("有事件撞到電視的去重鍵，會被靜靜吃掉一格")
    # 每一格都要走到 verdict，否則電視的 liveAssemble 會一直等
    opened = {e["task_id"] for e in evs if e["type"] == "task_opened"}
    settled = {e["task_id"] for e in evs if e["type"] == "verdict"}
    for t in sorted(opened - settled):
        bad.append(f"{t} 開了但沒有 verdict：電視會一直等這一格")
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
    print("  沒發的 type（因為這一批沒發生）：review_vote／revised／audited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
