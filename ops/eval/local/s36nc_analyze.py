"""S36-nocap 的判定與描述（裁決 BIGGER_EFFECT §十一；2026-09-27）：只讀這一批每一跑的評分、pi 事件流與 Vacant 病歷。

判準（跑之前寫死）：兩次合起來 72 對，`淨增對＝C 單獨對 − A 單獨對`、`多出來的錯＝C 答錯 − A 答錯`（答錯＝有答案檔、評分 0）。
**GO**：淨增對 ≥ 4、多出來的錯 ≤ 淨增對、傷害 0 次、C 的缺檔退回 ≥ 3 次。**STOP**：淨增對 ≤ 1 或傷害 ≥ 1。其餘＝不判定。
**傷害**＝C 第一次被退回的那一刻，答案檔已經寫了、而且那個值評分器會收，最後卻是錯的。
「退回那一刻答案檔裡是什麼」從 pi 事件流重建：退回（`entry_appended` 的 `custom_message`、`customType＝vacant-check`、`Before delivery:` 開頭）之前最後一次寫 `answer.txt` 的值
（`write` 的內容，或 bash 裡 `echo／printf … > …answer.txt`）；重建不出來就記 `None`、照實列出。

    python3 ops/eval/local/s36nc_analyze.py --jobs <s36nc jobs> --dataset <釘死的 formal 題目目錄> --out <json>

`--c-arm`（預設 `C36`）換成別的組名時，同一套描述（退回、傷害、沒交）照算，但**不套上面的判準**（那是 S36-nocap 專用的；
輸出沒有 `decision`）——例如沒用過的題的預註冊批次（`PREREG_20260927_NOCAP_UNSEEN`），它的主要檢定在 `analyze_local.py`。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ops" / "eval" / "formal"))
from analyze import score  # type: ignore[import-not-found]  # noqa: E402

from vacant_network.research import mcnemar_exact  # noqa: E402

ECHO = re.compile(r"(?:echo|printf)\s+(?:-[ne]+\s+)?(['\"]?)(.*?)\1\s*>\s*\S*answer\.txt", re.S)


def _text(c: Any) -> str:
    if isinstance(c, str):
        return c
    return "".join(x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text")


def one(trial: pathlib.Path, dataset: pathlib.Path, task: str) -> dict[str, Any]:
    try:
        reward = float((trial / "verifier" / "reward.txt").read_text().strip())
    except (OSError, ValueError):
        reward = None
    vt = trial / "verifier" / "test-stdout.txt"
    missing = vt.is_file() and "answer.txt not found" in vt.read_text(errors="replace")
    exc = (json.loads((trial / "result.json").read_text()).get("exception_info") or {}).get("exception_type")
    ev = []
    for ln in (trial / "agent" / "pi.txt").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            ev.append(json.loads(ln))
        except ValueError:
            continue
    writes: list[tuple[int, str | None]] = []
    first_sendback = None
    said_done_no_file_before_sb = None
    stops = []
    for i, e in enumerate(ev):
        t = e.get("type")
        if t == "tool_execution_start":
            a = e.get("args") or {}
            name = e.get("toolName")
            if name == "write" and str(a.get("path", "")).endswith("answer.txt"):
                writes.append((i, str(a.get("content") or "").strip()))
            elif name == "bash" and "answer.txt" in str(a.get("command") or ""):
                m = ECHO.search(str(a.get("command")))
                if m or re.search(r">\s*\S*answer\.txt", str(a.get("command"))):
                    writes.append((i, m.group(2).replace("\\n", "").strip() if m else None))
        if t == "entry_appended" and first_sendback is None:
            en = e.get("entry") or {}                   # pi 把擴充送的訊息記成 custom_message，不是 message_end
            if en.get("type") == "custom_message" and en.get("customType") == "vacant-check" \
                    and _text(en.get("content")).startswith("Before delivery"):
                first_sendback = i
                said_done_no_file_before_sb = not writes
        if t == "turn_end":
            stops.append((e.get("message") or {}).get("stopReason"))
    before = [w for w in writes if first_sendback is not None and w[0] < first_sendback]
    val_before = before[-1][1] if before else None
    ok_before = score(dataset, task, val_before) if val_before is not None else None
    kinds: list[tuple[str, list[str]]] = []
    for ch in trial.glob("agent/vacant_home/trace/projects/*/chain.ndjson"):
        for ln in ch.read_text().splitlines():
            d = json.loads(ln)
            if d.get("type") == "review":
                p = d.get("payload") or {}
                kinds.append((p.get("action"), [f.get("kind") for f in p.get("findings") or []]))
    return {"reward": reward, "missing": missing, "exception": exc, "turns": len(stops),
            "final_stop": stops[-1] if stops else None,
            "sendbacks": [k for a, k in kinds if a == "continue"], "reviews": len(kinds),
            "first_sendback": first_sendback is not None, "answer_at_first_sendback": val_before,
            "answer_at_first_sendback_ok": ok_before, "no_file_at_first_sendback": said_done_no_file_before_sb}


def lab(r: dict[str, Any]) -> str:
    return "right" if r["reward"] == 1.0 else ("no_file" if r["missing"] else "wrong")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--c-arm", default="C36")
    a = ap.parse_args(argv)
    C = a.c_arm
    cells: dict[tuple[str, str, int], dict[str, Any]] = {}
    for trial in sorted(a.jobs.glob("g12-off-*-s*/*/dabstep-*__*")):
        if not (trial / "result.json").is_file():
            continue
        m = re.search(r"g12-off-(\w+)-s(\d)/.*dabstep-(\d+)__", str(trial))
        arm, s, task = m.group(1), int(m.group(2)), m.group(3)
        cells[(task, arm, s)] = one(trial, a.dataset, task) | {"task": task, "arm": arm, "sample": s}
    pairs = [(t, s) for (t, arm, s) in cells if arm == "A" and (t, C, s) in cells]
    c_only = sum(1 for t, s in pairs if lab(cells[(t, C, s)]) == "right" and lab(cells[(t, "A", s)]) != "right")
    a_only = sum(1 for t, s in pairs if lab(cells[(t, "A", s)]) == "right" and lab(cells[(t, C, s)]) != "right")
    tally = {arm: collections.Counter(lab(r) for (t, ar, s), r in cells.items() if ar == arm) for arm in ("A", C)}
    extra_wrong = tally[C]["wrong"] - tally["A"]["wrong"]
    net = c_only - a_only
    c_runs = [r for r in cells.values() if r["arm"] == C]
    mo = [r for r in c_runs if any("missing_output" in k for k in r["sendbacks"])]
    harm = [r for r in c_runs if r["first_sendback"] and r["answer_at_first_sendback_ok"] == 1 and lab(r) != "right"]
    unknown_before = [r for r in c_runs if r["first_sendback"] and r["answer_at_first_sendback"] is None
                      and not r["no_file_at_first_sendback"] and lab(r) != "right"]
    if net >= 4 and extra_wrong <= net and not harm and len(mo) >= 3:
        decision = "GO"
    elif net <= 1 or harm:
        decision = "STOP"
    else:
        decision = "NOT DECIDED (underpowered)"
    kinds = collections.Counter(k for r in c_runs for ks in r["sendbacks"] for k in set(ks))
    after = collections.Counter((k, lab(r)) for r in c_runs for k in {k for ks in r["sendbacks"] for k in ks})
    a_runs = [r for r in cells.values() if r["arm"] == "A"]
    by_sb = collections.Counter(
        ("+".join(sorted({k for ks in cells[(t, C, s)]["sendbacks"] for k in ks})) or "none",
         lab(cells[(t, C, s)]), lab(cells[(t, "A", s)])) for t, s in pairs)
    unseen = [{"task": r["task"], "sample": r["sample"]} for r in c_runs if bool(r["sendbacks"]) != r["first_sendback"]]
    out = {
        "pairs": len(pairs), "C_only_right": c_only, "A_only_right": a_only, "net_right": net,
        "mcnemar_p_descriptive": mcnemar_exact(c_only, a_only),
        "tally": {k: dict(v) for k, v in tally.items()}, "extra_wrong": extra_wrong,
        "per_sample": {s: {arm: dict(collections.Counter(lab(r) for (t, ar, ss), r in cells.items() if ar == arm and ss == s))
                           for arm in ("A", C)} for s in sorted({k[2] for k in cells})},
        "C_runs_with_a_sendback": sum(1 for r in c_runs if r["sendbacks"]),
        "C_missing_output_sendback_runs": len(mo), "sendback_kinds_runs": dict(kinds),
        "end_state_after_sendback_kind": {f"{k}:{v}": n for (k, v), n in sorted(after.items())},
        "pairs_by_C_sendback_C_label_A_label": {"|".join(k): n for k, n in sorted(by_sb.items())},
        "sendback_chain_vs_stream_mismatch": unseen,
        "harm": [{"task": r["task"], "sample": r["sample"], "answer_before": r["answer_at_first_sendback"]} for r in harm],
        "sendback_ended_wrong_value_before_unknown": [{"task": r["task"], "sample": r["sample"]} for r in unknown_before],
        "A_said_done_without_file": sum(1 for r in a_runs if r["final_stop"] == "stop" and r["missing"]),
        "A_runs": len(a_runs),
        "timeouts": {arm: sum(1 for r in cells.values() if r["arm"] == arm and r["exception"] == "AgentTimeoutError")
                     for arm in ("A", C)},
    }
    if C == "C36":
        out["decision"] = decision                      # 只有 S36-nocap 的判準

    print(json.dumps(out, ensure_ascii=False, indent=1))
    if a.out:
        a.out.write_text(json.dumps({"summary": out, "cells": [dict(v, key=list(k)) for k, v in cells.items()]},
                                    ensure_ascii=False, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
