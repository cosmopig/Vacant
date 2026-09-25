"""DABstep 正式批次的分析（`decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md` 第三、四節）。
**開跑之前寫好、commit**；批次結束之後跑一次。

    python3 ops/eval/formal/analyze.py --jobs <jobs 根目錄> --ledger <代理 ledger 目錄> \
        --dataset <正式題目目錄> --out <輸出目錄>

主要比較：gemma（`g4`）開思考，C 對 A，77 題（去掉 5、70），只用兩邊都有評分的題，McNemar 精確雙尾
（`vacant_network.research.mcnemar_exact`）。其餘（qwen、第 5／70 題、翻轉、傷害、退回、成本、時間）只描述。

「傷害」：C 組第一次 Stop（第一個 `review` 事件）時工作區裡的 `answer.txt`，用那一題自己的 `tests/scorer.py`
照 `test.sh` 的方式（第一行、去頭尾空白）評分；第一次是對的、最後是錯的＝傷害。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from vacant_network.research import mcnemar_exact  # noqa: E402
from vacant_network.trace.blame import Trace  # noqa: E402
from vacant_network.trace.recorder import Recorder  # noqa: E402

EXCLUDED = {"5", "70"}
PRIMARY = ("g4", "on")


def expected(dataset: pathlib.Path, task: str) -> str:
    t = (dataset / f"dabstep-{task}" / "tests" / "test.sh").read_text()
    body = t.split("<<'ANSWER_EOF'\n", 1)[1].split("\nANSWER_EOF", 1)[0]
    return body.strip()


def score(dataset: pathlib.Path, task: str, answer: str | None) -> int | None:
    if answer is None:
        return 0
    first = (answer.splitlines() or [""])[0].strip()
    p = subprocess.run([sys.executable, str(dataset / f"dabstep-{task}" / "tests" / "scorer.py"),
                        first, expected(dataset, task)], capture_output=True, timeout=60)
    return 1 if p.returncode == 0 else 0


def first_stop(trial: pathlib.Path) -> dict[str, Any]:
    """C 組：第一次交件前檢查時的答案、有沒有退回、退回了哪幾類。"""
    vh = trial / "agent" / "vacant_home" / "trace"
    out: dict[str, Any] = {"reviews": 0, "sent_back": False, "kinds": [], "first_answer": None,
                           "first_answer_exists": None}
    if not vh.is_dir():
        return out
    rec = Recorder("/app", root=vh)
    if not rec.chain_path.is_file():
        return out
    tr = Trace(rec)
    evs = [e for e in rec.events() if e["type"] == "review"]
    out["reviews"] = len(evs)
    if not evs:
        return out
    first = evs[0]
    out["sent_back"] = first.get("action") == "continue"
    out["kinds"] = sorted({f.get("kind") for e in evs if e.get("action") == "continue"
                           for f in e.get("findings") or [] if f.get("finding_id") in (e.get("sent") or [])})
    before = [s for s in tr.steps if s.seq < first["seq"]]
    idx = before[-1].post_index if before and before[-1].post_index else tr.initial
    txt = tr.file_text(idx, "answer.txt") if idx else None
    out["first_answer"] = txt
    out["first_answer_exists"] = txt is not None
    return out


def runs(jobs: pathlib.Path, ledger: pathlib.Path, dataset: pathlib.Path) -> list[dict[str, Any]]:
    by_tag = json.loads((ledger / "summary.json").read_text()).get("by_tag", {})
    led = [json.loads(x) for x in (ledger / "ledger.jsonl").read_text().splitlines() if x.strip()]
    errs: dict[str, int] = {}
    for r in led:
        if r.get("status") != 200 or r.get("stream_error"):
            errs[r["tag"]] = errs.get(r["tag"], 0) + 1
    out = []
    for res in sorted(jobs.glob("*/*/dabstep-*__*/result.json")):
        trial = res.parent
        m, think, arm = trial.parents[1].name.split("-")
        task = trial.name.split("__")[0].removeprefix("dabstep-")
        r = json.loads(res.read_text())
        vr = r.get("verifier_result") or {}
        reward = (vr.get("rewards") or {}).get("reward", vr.get("reward"))
        exc = (r.get("exception_info") or {}).get("exception_type")
        tag = f"formal-{m}-{think}-{arm}-{task}"
        lg = by_tag.get(tag) or {}
        row: dict[str, Any] = {
            "task": task, "model": m, "think": think, "arm": arm, "trial": trial.name,
            "reward": reward, "exception": exc, "requests": lg.get("requests"),
            "provider_errors": errs.get(tag, 0), "prompt_tokens": lg.get("prompt_tokens"),
            "completion_tokens": lg.get("completion_tokens"),
            "reasoning_tokens": lg.get("reasoning_tokens"), "cost_usd": lg.get("cost_usd"),
            "started": r.get("started_at"), "finished": r.get("finished_at")}
        # 一跑壞掉：沒有評分，或模型一個回答都沒拿到（請求全是供應商錯誤）
        row["infra_void"] = reward is None or (bool(lg.get("requests")) and
                                               errs.get(tag, 0) >= int(lg.get("requests") or 0))
        if arm == "C":
            chk = trial / "agent" / "vacant_check.json"
            try:
                row["vacant_check"] = json.loads(chk.read_text().strip().splitlines()[-1])
            except (OSError, ValueError, IndexError):
                row["vacant_check"] = None
            fs = first_stop(trial)
            fs["first_score"] = score(dataset, task, fs["first_answer"]) if fs["reviews"] else None
            row["first_stop"] = {k: v for k, v in fs.items() if k != "first_answer"}
            row["first_answer"] = (fs["first_answer"] or "")[:200] if fs["first_answer"] else None
        out.append(row)
    return out


def pairs(rows: list[dict[str, Any]], m: str, think: str) -> dict[str, dict[str, dict]]:
    """每一題一對；同一格有多跑（補跑）時用最後一跑。"""
    by: dict[str, dict[str, dict]] = {}
    for r in sorted(rows, key=lambda x: x["trial"]):
        if r["model"] == m and r["think"] == think:
            by.setdefault(r["task"], {})[r["arm"]] = r
    return by


def compare(by: dict[str, dict[str, dict]], tasks: set[str] | None) -> dict[str, Any]:
    b = c = both = neither = 0
    flips = []
    used = void = 0
    for t, arms in sorted(by.items(), key=lambda kv: int(kv[0])):
        if tasks is not None and t not in tasks:
            continue
        a, cc = arms.get("A"), arms.get("C")
        if not a or not cc:
            continue
        if a["infra_void"] or cc["infra_void"]:
            void += 1
            continue
        used += 1
        ra, rc = int(a["reward"] or 0), int(cc["reward"] or 0)
        if ra and rc:
            both += 1
        elif not ra and not rc:
            neither += 1
        elif rc:
            b += 1
            flips.append({"task": t, "A": 0, "C": 1})
        else:
            c += 1
            flips.append({"task": t, "A": 1, "C": 0})
    return {"pairs": used, "void_pairs": void, "A_correct": both + c, "C_correct": both + b,
            "C_only": b, "A_only": c, "both": both, "neither": neither,
            "mcnemar_p": mcnemar_exact(b, c), "flips": flips}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows = runs(a.jobs, a.ledger, a.dataset)
    allt = {r["task"] for r in rows}
    result: dict[str, Any] = {"prereg": "decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md"}
    for m, think in (("g4", "on"), ("q38", "on")):
        by = pairs(rows, m, think)
        cond = f"{m}-{think}"
        main77 = compare(by, allt - EXCLUDED)
        c_rows = [r for r in rows if r["model"] == m and r["think"] == think and r["arm"] == "C"]
        harm = [r["task"] for r in c_rows if (r.get("first_stop") or {}).get("sent_back")
                and (r.get("first_stop") or {}).get("first_score") == 1 and r.get("reward") == 0]
        helped_by_pushback = [r["task"] for r in c_rows if (r.get("first_stop") or {}).get("sent_back")
                              and (r.get("first_stop") or {}).get("first_score") == 0
                              and r.get("reward") == 1]
        kinds: dict[str, int] = {}
        for r in c_rows:
            for k in (r.get("first_stop") or {}).get("kinds") or []:
                kinds[k] = kinds.get(k, 0) + 1
        cost = {arm: round(sum(r["cost_usd"] or 0 for r in rows if r["model"] == m
                               and r["think"] == think and r["arm"] == arm), 6) for arm in "AC"}
        result[cond] = {
            "primary": (m, think) == PRIMARY,
            "tasks_77": main77,
            "tasks_5_70": compare(by, EXCLUDED),
            "c_runs": len(c_rows),
            "c_stop_reached": sum(1 for r in c_rows if (r.get("vacant_check") or {}).get("stop_reached")),
            "c_arm_ok_false": [r["task"] for r in c_rows if not (r.get("vacant_check") or {}).get("c_arm_ok")],
            "c_sent_back": sum(1 for r in c_rows if (r.get("first_stop") or {}).get("sent_back")),
            "sent_back_kinds": kinds,
            "harm_first_right_then_wrong": harm,
            "pushback_first_wrong_then_right": helped_by_pushback,
            "cost_usd": cost,
            "requests": {arm: sum(r["requests"] or 0 for r in rows if r["model"] == m
                                  and r["think"] == think and r["arm"] == arm) for arm in "AC"},
            "provider_errors": {arm: sum(r["provider_errors"] for r in rows if r["model"] == m
                                         and r["think"] == think and r["arm"] == arm) for arm in "AC"},
        }
    (a.out / "runs.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
    (a.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
