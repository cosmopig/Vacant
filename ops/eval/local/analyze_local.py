"""本機算力批次的分析（2026-09-26）：`run_batch.py` 產生的 jobs 目錄 → 每一格的結果＋組別比較。

    python3 ops/eval/local/analyze_local.py --jobs <jobs 根目錄> --ledger <代理 ledger 目錄> \
        --dataset <釘死的題目目錄> --prefix <標籤前綴> --out <輸出目錄> [--primary C2:A]

每一格＝(題目, 組別, 第幾次)。重用 `ops/eval/formal/analyze.py` 的評分（`score`）與「第一次交件前檢查」的重建（`first_stop`）。
同一格有多跑時取 job 目錄時間上最後的一跑。主要分析用 77 題（去掉第 5、70 題，和付費批次一樣）。

輸出：
- `cells.json`：每一格的評分、例外、請求數、token、牆鐘、Vacant 的動作（走到檢查沒、退回沒、退回幾類、第一次交件時的答案對不對）。
- `summary.json`：每個組別每一次的答對數；同一組別兩次之間的翻轉（純運氣的翻轉率）；每一次內的配對 McNemar；
  跨次數的每題平均答對率的配對比較（符號檢定＋Wilcoxon 精確檢定）；Vacant 的動作統計與「第一次交件是對的卻被退回」的比例。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from itertools import combinations
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ops" / "eval" / "formal"))

from analyze import first_stop, score  # type: ignore[import-not-found]  # noqa: E402
from vacant_network.research import mcnemar_exact, wilcoxon_signed_rank_exact  # noqa: E402

EXCLUDED = {"5", "70"}


def cells(jobs: pathlib.Path, ledger: pathlib.Path, dataset: pathlib.Path, prefix: str) -> list[dict[str, Any]]:
    by_tag = json.loads((ledger / "summary.json").read_text()).get("by_tag", {})
    led = [json.loads(x) for x in (ledger / "ledger.jsonl").read_text().splitlines() if x.strip()]
    errs: dict[str, int] = {}
    ups: dict[str, str] = {}
    for r in led:
        if r.get("status") != 200 or r.get("stream_error"):
            errs[r["tag"]] = errs.get(r["tag"], 0) + 1
        if r.get("upstream"):
            ups[r["tag"]] = r["upstream"]
    latest: dict[tuple[str, str, int], dict[str, Any]] = {}
    for res in sorted(jobs.glob("g12-off-*-s*/*/dabstep-*__*/result.json")):
        trial = res.parent
        arm_dir = trial.parents[1].name                       # g12-off-<ARM>-s<k>
        arm, s = arm_dir.removeprefix("g12-off-").rsplit("-s", 1)
        task = trial.name.split("__")[0].removeprefix("dabstep-")
        r = json.loads(res.read_text())
        vr = r.get("verifier_result") or {}
        reward = (vr.get("rewards") or {}).get("reward", vr.get("reward"))
        tag = f"{prefix}-g12-off-{arm}-{task}-s{s}"
        lg = by_tag.get(tag) or {}
        row: dict[str, Any] = {
            "task": task, "arm": arm, "sample": int(s), "trial": trial.name, "job": trial.parent.name,
            "started": r.get("started_at"), "finished": r.get("finished_at"),
            "reward": reward, "exception": (r.get("exception_info") or {}).get("exception_type"),
            "requests": lg.get("requests"), "provider_errors": errs.get(tag, 0),
            "prompt_tokens": lg.get("prompt_tokens"), "completion_tokens": lg.get("completion_tokens"),
            "upstream": ups.get(tag)}
        row["infra_void"] = reward is None or (bool(lg.get("requests")) and
                                               errs.get(tag, 0) >= int(lg.get("requests") or 0))
        if arm != "A":
            try:
                row["vacant_check"] = json.loads((trial / "agent" / "vacant_check.json")
                                                 .read_text().strip().splitlines()[-1])
            except (OSError, ValueError, IndexError):
                row["vacant_check"] = None
            fs = first_stop(trial)
            fs["first_score"] = score(dataset, task, fs["first_answer"]) if fs["reviews"] else None
            row["first_stop"] = {k: v for k, v in fs.items() if k != "first_answer"}
        key = (task, arm, int(s))
        if key not in latest or row["started"] > latest[key]["started"]:
            latest[key] = row
    return sorted(latest.values(), key=lambda x: (int(x["task"]), x["arm"], x["sample"]))


def sign_test(pos: int, neg: int) -> float:
    return mcnemar_exact(pos, neg)                     # 同一個二項精確檢定


def summarize(rows: list[dict[str, Any]], primary: tuple[str, str] | None) -> dict[str, Any]:
    main = [r for r in rows if r["task"] not in EXCLUDED]
    arms = sorted({r["arm"] for r in main})
    samples = sorted({r["sample"] for r in main})
    cell = {(r["task"], r["arm"], r["sample"]): r for r in main}
    tasks = sorted({r["task"] for r in main}, key=int)
    ok = lambda r: int(bool(r and not r["infra_void"] and r["reward"]))  # noqa: E731
    out: dict[str, Any] = {"tasks": len(tasks), "arms": arms, "samples": samples, "per_arm_sample": {},
                           "noise_between_samples": {}, "paired_within_sample": {}, "pooled_per_task": {},
                           "vacant": {}}
    for arm in arms:
        for s in samples:
            rs = [cell.get((t, arm, s)) for t in tasks]
            out["per_arm_sample"][f"{arm}-s{s}"] = {
                "runs": sum(1 for r in rs if r), "correct": sum(ok(r) for r in rs),
                "infra_void": sum(1 for r in rs if r and r["infra_void"]),
                "no_answer": sum(1 for r in rs if r and not r["infra_void"] and not r["reward"]
                                 and (r.get("first_stop") or {}).get("first_answer_exists") is not True)}
        for s1, s2 in combinations(samples, 2):
            b = c = n = 0
            for t in tasks:
                x, y = cell.get((t, arm, s1)), cell.get((t, arm, s2))
                if not x or not y or x["infra_void"] or y["infra_void"]:
                    continue
                n += 1
                b += int(ok(y) and not ok(x))
                c += int(ok(x) and not ok(y))
            out["noise_between_samples"][f"{arm}:s{s1}-s{s2}"] = {"pairs": n, "flips": b + c, "b": b, "c": c}
    for x, y in combinations(arms, 2):
        for s in samples:
            b = c = n = 0
            for t in tasks:
                p, q = cell.get((t, x, s)), cell.get((t, y, s))
                if not p or not q or p["infra_void"] or q["infra_void"]:
                    continue
                n += 1
                b += int(ok(q) and not ok(p))
                c += int(ok(p) and not ok(q))
            out["paired_within_sample"][f"{y}_vs_{x}-s{s}"] = {"pairs": n, f"only_{y}": b, f"only_{x}": c,
                                                             "mcnemar_p": mcnemar_exact(b, c)}
        diffs = []
        for t in tasks:
            px = [ok(cell[(t, x, s)]) for s in samples if (t, x, s) in cell and not cell[(t, x, s)]["infra_void"]]
            py = [ok(cell[(t, y, s)]) for s in samples if (t, y, s) in cell and not cell[(t, y, s)]["infra_void"]]
            if px and py:
                diffs.append(sum(py) / len(py) - sum(px) / len(px))
        pos, neg = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
        wil = wilcoxon_signed_rank_exact([d for d in diffs if d != 0]) if any(diffs) else None
        out["pooled_per_task"][f"{y}_vs_{x}"] = {
            "tasks": len(diffs), "mean_diff": round(sum(diffs) / len(diffs), 4) if diffs else None,
            "tasks_better": pos, "tasks_worse": neg, "sign_p": sign_test(pos, neg), "wilcoxon": wil}
    for arm in arms:
        if arm == "A":
            continue
        rs = [r for r in main if r["arm"] == arm and not r["infra_void"]]
        fs = [r.get("first_stop") or {} for r in rs]
        reached = [f for f in fs if f.get("reviews")]
        right_first = [f for f in reached if f.get("first_score") == 1]
        kinds: dict[str, int] = {}
        for f in fs:
            for k in f.get("kinds") or []:
                kinds[k] = kinds.get(k, 0) + 1
        out["vacant"][arm] = {
            "runs": len(rs), "stop_reached": len(reached),
            "sent_back": sum(1 for f in reached if f.get("sent_back")), "kinds": kinds,
            "correct_first_answers": len(right_first),
            "correct_first_answers_sent_back": sum(1 for f in right_first if f.get("sent_back")),
            "sent_back_then_right": sum(1 for r in rs if (r.get("first_stop") or {}).get("sent_back")
                                        and (r.get("first_stop") or {}).get("first_score") == 0 and r["reward"]),
            "sent_back_then_wrong_from_right": sum(1 for r in rs if (r.get("first_stop") or {}).get("sent_back")
                                                   and (r.get("first_stop") or {}).get("first_score") == 1
                                                   and not r["reward"]),
            "install_failed": sum(1 for r in rs if not (r.get("vacant_check") or {}).get("c_arm_ok"))}
    if primary:
        out["primary"] = {"comparison": f"{primary[0]}_vs_{primary[1]}",
                          "result": out["pooled_per_task"].get(f"{primary[0]}_vs_{primary[1]}")
                          or out["pooled_per_task"].get(f"{primary[1]}_vs_{primary[0]}")}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--ledger", required=True, type=pathlib.Path)
    ap.add_argument("--dataset", required=True, type=pathlib.Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--primary", help="例如 C2:A（前者對後者）")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows = cells(a.jobs, a.ledger, a.dataset, a.prefix)
    prim = tuple(a.primary.split(":")) if a.primary else None
    summ = summarize(rows, prim)  # type: ignore[arg-type]
    (a.out / "cells.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
    (a.out / "summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(summ, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
