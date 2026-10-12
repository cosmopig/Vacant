"""把「還沒說做完就結束」的交件說明分成兩種（**事後、描述，不是檢定**；2026-09-26）。

為什麼有這一支：凍結的 v3（正式批次 C2 用的那一版）只要這個要求裡沒有交件前檢查的紀錄就寫「Ended before the agent said it was
done」。但 Harbor 的回合上限在它自己的回合結束處理器裡中止，所以 agent **在最後一回合交最終答案**時 pi 也不進交件前檢查——
那一跑其實說了做完（審查 `ops/eval/evidence_20260926_local/review_v3/`，裁決 `decisions/DECISION_20260926_ZERO_CONFIG_V3.md` §七）。
預註冊的描述項照凍結的 `analyze_local.py` 算；這一支只把那個數字拆開：

- `final_answer_on_last_turn`：pi 事件流裡最後一個真的回合（不算中止之後 pi 補的那個空回合）沒有工具結果、`stopReason` 是 `stop`；
- `cut_off`：其他（最後一個回合還在執行工具，或被中止）。

只讀 jobs 目錄裡每一跑的 `agent/pi.txt` 與 `agent/vacant_check.json`，不讀評分以外的任何東西；評分只拿來分開列。

    python3 ops/eval/local/split_ended.py --jobs <jobs 根目錄> [--arm C2] [--out <json>]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any


def last_turn(pi_txt: pathlib.Path) -> dict[str, Any]:
    """最後一個真的回合：`stopReason`、工具結果數、回合數（中止之後的 `error` 空回合不算）。"""
    turns: list[tuple[str | None, int]] = []
    try:
        lines = pi_txt.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"turns": None, "stop_reason": None, "tool_results": None}
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("type") != "turn_end":
            continue
        m = r.get("message") or {}
        turns.append((m.get("stopReason"), len(r.get("toolResults") or [])))
    real = list(turns)
    while len(real) > 1 and real[-1][0] in ("error", "aborted") and real[-1][1] == 0:
        real.pop()                       # 中止之後 pi 補的那一個空回合
    if not real:
        return {"turns": 0, "stop_reason": None, "tool_results": None}
    sr, n = real[-1]
    return {"turns": len(real), "stop_reason": sr, "tool_results": n}


def runs(jobs: pathlib.Path, arm: str) -> list[dict[str, Any]]:
    out = []
    for trial in sorted(jobs.glob(f"g12-off-{arm}-s*/*/dabstep-*__*")):
        chk = trial / "agent" / "vacant_check.json"
        try:
            v = json.loads(chk.read_text().strip().splitlines()[-1])
        except (OSError, ValueError, IndexError):
            v = {}
        m = re.search(r"-(\d+)-s(\d+)$", trial.parent.name)
        reward = None
        try:
            reward = float((trial / "verifier" / "reward.txt").read_text().strip())
        except (OSError, ValueError):
            pass
        lt = last_turn(trial / "agent" / "pi.txt")
        final = lt["stop_reason"] == "stop" and lt["tool_results"] == 0
        out.append({"task": m.group(1) if m else None, "sample": int(m.group(2)) if m else None,
                    "ended_notes": int(v.get("ended_notes") or 0), "reviews": int(v.get("reviews") or 0),
                    "nudge_turns": v.get("nudge_turns") or [], "reward": reward, **lt,
                    "kind": ("final_answer_on_last_turn" if final else "cut_off")
                    if int(v.get("ended_notes") or 0) else None})
    return out


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ended = [r for r in rows if r["ended_notes"]]
    by: dict[str, Any] = {}
    for k in ("final_answer_on_last_turn", "cut_off"):
        g = [r for r in ended if r["kind"] == k]
        by[k] = {"n": len(g), "reward_1": sum(1 for r in g if r["reward"] == 1.0),
                 "nudged": sum(1 for r in g if r["nudge_turns"]),
                 "runs": [f"{r['task']}-s{r['sample']}" for r in g]}
    return {"runs": len(rows), "ended_notes": len(ended), **by}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--arm", default="C2")
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    rows = runs(a.jobs, a.arm)
    s = summarize(rows)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    if a.out:
        a.out.write_text(json.dumps({"summary": s, "rows": rows}, ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
