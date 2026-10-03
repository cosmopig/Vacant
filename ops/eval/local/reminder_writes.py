"""提醒之後才寫的答案：有沒有出處、有沒有答對（描述；留出批次預註冊第六節；2026-09-26）。

v3.3 起，交件說明（`delivery.json`）記下哪些檔是回合預算提醒**之後**才寫的（`written_after_reminder`），以及
「寫出來的行裡有幾個值被對照過、幾個在讀過或跑過的東西裡找得到」（`checked`）。這一支把每一個有裝 Vacant 的跑讀出來、
配上評分，分成：

- `reminded_write_sourced`：提醒之後寫的，而且裡面的值在紀錄裡找得到（讀過／跑過的輸出、能從讀過的表算出來）；
- `reminded_write_unsourced`：提醒之後寫的，但沒有一個值被對照過或找得到（文字答案、猜的數字）——答對也當成**猜中**，不當成提醒的功勞；
- `no_reminded_write`：沒有提醒，或提醒之後沒寫。

只讀 jobs 目錄裡每一跑的 `agent/vacant_home/trace/projects/*/delivery.json`、`agent/vacant_check.json` 與評分。

    python3 ops/eval/local/reminder_writes.py --jobs <jobs 根目錄> --arm C3 [--out <json>]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any


def one(trial: pathlib.Path) -> dict[str, Any]:
    notes = sorted(trial.glob("agent/vacant_home/trace/projects/*/delivery.json"))
    note: dict[str, Any] = {}
    if notes:
        try:
            note = json.loads(notes[-1].read_text())
        except (OSError, ValueError):
            note = {}
    reward = None
    try:
        reward = float((trial / "verifier" / "reward.txt").read_text().strip())
    except (OSError, ValueError):
        pass
    try:
        chk = json.loads((trial / "agent" / "vacant_check.json").read_text().strip().splitlines()[-1])
    except (OSError, ValueError, IndexError):
        chk = {}
    written = [w.get("path") for w in note.get("written_after_reminder") or []]
    v = note.get("checked") or {}
    sourced = int(v.get("traced") or 0) + int(v.get("derived") or 0) > 0
    kind = ("no_reminded_write" if not written else
            "reminded_write_sourced" if sourced else "reminded_write_unsourced")
    m = re.search(r"-(\d+)-s(\d+)$", trial.parent.name)
    return {"task": m.group(1) if m else None, "sample": int(m.group(2)) if m else None,
            "reward": reward, "nudges": chk.get("nudges"), "written_after_reminder": written,
            "values_checked": v, "checked_after_end": bool(note.get("checked_after_end")), "kind": kind}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--arm", default="C3")
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    rows = [one(t) for t in sorted(a.jobs.glob(f"g12-off-{a.arm}-s*/*/dabstep-*__*"))
            if (t / "result.json").is_file()]
    summ: dict[str, Any] = {"runs": len(rows)}
    for k in ("reminded_write_sourced", "reminded_write_unsourced", "no_reminded_write"):
        g = [r for r in rows if r["kind"] == k]
        summ[k] = {"runs": len(g), "reward_1": sum(1 for r in g if r["reward"] == 1.0)}
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    if a.out:
        a.out.write_text(json.dumps({"summary": summ, "rows": rows}, ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
