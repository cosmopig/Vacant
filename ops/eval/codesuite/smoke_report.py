"""程式題篩選組的冒煙報告（2026-09-26）：每一跑的結束方式、自己跑的測試、最後一次測試的結束碼、評分（描述）。

候選 2（`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §二）要的是「**最後一次自己跑的測試失敗、之後沒再改、卻說做完**」——
這一支只量那種情形**多常出現**（沒有它，候選 2 在這個題組上沒有東西可以作用），不判斷 Vacant 該不該退回。

只讀每一跑的 `agent/pi.txt`（pi 的事件流）與 `verifier/reward.txt`：
- **測試執行**：bash 工具呼叫、指令裡有 `unittest`／`pytest`／`test_public`；結束碼取 pi 附在輸出最後的 `exited with code N`，
  沒有這一行且 `isError` 為假 ⇒ 0；`isError` 為真但讀不出碼 ⇒ `None`（不知道）。
- **之後有沒有改**：最後一次測試之後有沒有 `write`／`edit` 工具呼叫，或 bash 指令裡出現 `solution.py` 且有 `>`／`tee`／`sed -i`／`cat <<`。
- **說做完**：pi 的最後一則助理訊息 `stopReason == "stop"`（不是 `error`／`aborted`＝被回合上限或時限切斷）。

    python3 ops/eval/codesuite/smoke_report.py --jobs <jobs 根目錄> [--out <json>]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
from typing import Any

TEST_RE = re.compile(r"unittest|pytest|test_public")
EXIT_RE = re.compile(r"exited with code (\d+)")
WRITE_BASH_RE = re.compile(r"solution\.py")
REDIRECT_RE = re.compile(r">|\btee\b|sed\s+-i|cat\s+<<")


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(c.get("text") or "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")


def one(trial: pathlib.Path) -> dict[str, Any]:
    events = []
    try:
        for ln in (trial / "agent" / "pi.txt").read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                events.append(json.loads(ln))
            except ValueError:
                continue
    except OSError:
        pass
    starts: dict[str, dict[str, Any]] = {}
    steps: list[dict[str, Any]] = []
    for e in events:
        if e.get("type") == "tool_execution_start":
            starts[str(e.get("toolCallId"))] = e
        elif e.get("type") == "tool_execution_end":
            s = starts.get(str(e.get("toolCallId"))) or {}
            args = s.get("args") or {}
            out = _text((e.get("result") or {}).get("content"))
            m = EXIT_RE.findall(out[-400:])
            code = int(m[-1]) if m else (None if e.get("isError") else 0)
            steps.append({"tool": e.get("toolName"), "command": str(args.get("command") or ""),
                          "path": str(args.get("path") or ""), "exit": code})
    tests = [i for i, s in enumerate(steps) if s["tool"] == "bash" and TEST_RE.search(s["command"])]
    last = tests[-1] if tests else None
    changed_after = last is not None and any(
        s["tool"] in ("write", "edit") or (s["tool"] == "bash" and WRITE_BASH_RE.search(s["command"])
                                           and REDIRECT_RE.search(s["command"]))
        for s in steps[last + 1:])
    stop = None
    for e in reversed(events):
        if e.get("type") == "agent_end":
            msgs = [m for m in e.get("messages") or [] if m.get("role") == "assistant"]
            stop = msgs[-1].get("stopReason") if msgs else None
            break
    reward = None
    try:
        reward = float((trial / "verifier" / "reward.txt").read_text().strip())
    except (OSError, ValueError):
        pass
    turns = sum(1 for e in events if e.get("type") == "turn_end")
    last_exit = steps[last]["exit"] if last is not None else None
    said_done = stop == "stop"
    if not said_done:
        kind = "not_done"
    elif last is None:
        kind = "done_no_test"
    elif last_exit is None:
        kind = "done_last_test_unknown"
    elif last_exit != 0 and not changed_after:
        kind = "done_last_test_failed"          # 候選 2 的目標
    elif last_exit != 0:
        kind = "done_last_test_failed_then_changed"
    elif changed_after:
        kind = "done_last_test_passed_then_changed"
    else:
        kind = "done_last_test_passed"
    return {"trial": trial.name, "arm_dir": trial.parent.parent.name, "reward": reward, "turns": turns, "stop": stop,
            "test_runs": len(tests), "last_test_exit": last_exit, "changed_after_last_test": changed_after, "kind": kind}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    rows = [one(t) for t in sorted(a.jobs.glob("g12-off-*-s*/*/*__*")) if (t / "result.json").is_file()]
    summ: dict[str, Any] = {"runs": len(rows)}
    by: dict[str, Any] = collections.defaultdict(lambda: {"runs": 0, "reward_1": 0})
    for r in rows:
        k = f"{r['arm_dir']}:{r['kind']}"
        by[k]["runs"] += 1
        by[k]["reward_1"] += r["reward"] == 1.0
    summ["by_kind"] = dict(sorted(by.items()))
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    if a.out:
        a.out.write_text(json.dumps({"summary": summ, "rows": rows}, ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
