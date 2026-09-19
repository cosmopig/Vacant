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
EMITTED = ("task_opened", "routed", "draft_done", "gate_ran", "revised",
           "verdict", "receipt", "counters")

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
        ev("draft_done", worker=cell["resident"],
           calls_used=int(a.get("requests_seen") or 0),
           attempt=n, of=n_total,
           # 回饋真的進了幾個位元組。第 1 次恆為 0 ⇒「與沒有 Vacant 時逐位元
           # 相同」這件事在資料上自己說得出來。
           feedback_bytes=a.get("feedback_in_prompt_bytes"))
        vis = a.get("visible")
        if vis is None:
            # 沒有閘門結果（沒有驗收套件／基建中止）⇒ **不發 gate_ran**。
            continue
        failed = next((c["case"] for c in (vis.get("cases") or [])
                       if not c["ok"]), None)
        ev("gate_ran", passed=bool(vis.get("all_pass")),
           n_tests=vis.get("total"), failed_case=failed,
           attempt=n, of=n_total)
        if i + 1 < n_total:
            # 下一次嘗試存在 ⇒ 這一次沒過而且還有額度。
            # ⚠ reviser ＝ **同一個 worker**（誠實邊界 4）。
            ev("revised", reviser=cell["resident"],
               transition=TRANSITION.get(retry_arm, retry_arm),
               arm=retry_arm, attempt=n + 1, of=n_total)

    accepted = _signed_accepted(cell)
    stop = cell.get("stop_reason") or ""
    ev("verdict",
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
    ev("receipt", sha256=head, chain_head=head, verify_url=verify_url,
       # ⚠ 契約的 `sha256` 是**收據**的，電視 v1 卻把它塞進一個叫
       #   `prompt_sha256` 的欄位（world3_patch 的第 2 條）。這兩個
       #   hash 各自帶一份，patch 過的電視才有東西可以分開顯示。
       prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
       verdict_sha256=cell.get("verdict_sha256"),
       ws_end_sha256=cell.get("ws_end_sha256"))
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
    evs.append({
        "type": "counters", "ts": iso(ts), "task_id": "-",
        "blocked": pack["refused"], "total": len(pack["cells"]),
        "delivered": pack["delivered"],
        "evidence_counts": dict(sorted(levels.items())),
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
