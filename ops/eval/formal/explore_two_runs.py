"""探索性（**不是預註冊的檢定**，2026-09-26 事後寫）：把正式批次每一題的 A、C 兩跑當成「同一題的兩次獨立作答」，
估兩件事——

1. **沒寫答案就重開一跑**：第一跑結束時沒有答案檔，就再開一個全新的一跑、用它的答案。
   用 C 組那一跑當第二跑。Vacant 在 C 組改了 8 跑的輸入（退回）；其中第 62、1753 題（gemma）A 沒有答案檔，
   所以這兩跑被當成第二跑用到——兩跑退回前後答案都沒變（`runs.json` 的 `first_stop.first_score` 等於最後的評分），
   不影響結果，但它們不是「完全沒被 Vacant 動過」的第二跑。
   ⚠ 這個規則按構造不會少掉任何一題（第一跑有答案就用第一跑），所以「多了幾題、少了 0 題」不是檢定，不報 p 值。
2. **兩跑答案對不對得上**：兩跑都有答案時，用 DABstep 自己的評分程式互比（雙向都過才算一致）；
   一致時有多準、不一致的題裡藏了幾個錯的答案。

為什麼要算：這一輪的 C 組只能「在同一個工作階段裡退回」，而過去有增益的設定（CONFORM）是「檢查不過就重抽」。
這支用手上已經付過錢的兩跑，零花費地估「換成重抽」大概會怎樣。⚠ 同一批題、事後才想到、沒有獨立驗證——只能當方向，不能當證據。

    python3 ops/eval/formal/explore_two_runs.py --jobs <正式批次 jobs 根目錄> --runs <runs.json> \
        --scorer <任一題的 tests/scorer.py> --out <輸出 json>

jobs 根目錄可以從 `ops/eval/evidence_20260925/formal/formal_jobs.tar.xz` 解出來。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

EXCLUDED = {"5", "70"}


def got(jobs: pathlib.Path, r: dict[str, Any]) -> str | None:
    """評分程式讀到的答案（`Got:` 那一行）；沒有答案檔＝None。"""
    t = (jobs / r["job"] / r["trial"] / "verifier" / "test-stdout.txt").read_text()
    m = re.search(r"^Got: (.*)$", t, re.M)
    return m.group(1).strip() if m else None


def same(scorer: pathlib.Path, a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False

    def ok(x: str, y: str) -> bool:
        return subprocess.run([sys.executable, str(scorer), x, y], capture_output=True,
                              timeout=60).returncode == 0
    return ok(a, b) and ok(b, a)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, type=pathlib.Path)
    ap.add_argument("--runs", required=True, type=pathlib.Path)
    ap.add_argument("--scorer", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    rows = json.loads(a.runs.read_text())
    by: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in sorted(rows, key=lambda x: x["job"]):          # 同 analyze.py：補跑取時間上最後一跑
        by[(r["model"], r["arm"], r["task"])] = r
    result: dict[str, Any] = {"note": "探索性；同一批題、事後分析、不是預註冊的檢定", "models": {},
                              "second_run_after_pushback": "gemma 第 62、1753 題的 C 跑被退回過、又被當成第二跑；兩跑退回前後答案不變"}
    for m in ("g4", "q38"):
        tasks = sorted({t for (mm, _, t) in by if mm == m and t not in EXCLUDED}, key=int)
        pairs: list[dict[str, Any]] = []
        for t in tasks:
            A, C = by[(m, "A", t)], by[(m, "C", t)]
            ga, gc = got(a.jobs, A), got(a.jobs, C)
            pairs.append({"task": t, "A": ga, "C": gc, "A_ok": int(A["reward"] or 0),
                          "C_ok": int(C["reward"] or 0), "agree": same(a.scorer, ga, gc),
                          "A_cost": A["cost_usd"] or 0, "C_cost": C["cost_usd"] or 0,
                          "C_sent_back": bool((C.get("first_stop") or {}).get("sent_back"))})
        missing = [p for p in pairs if p["A"] is None]
        gained = [p["task"] for p in missing if p["C_ok"]]
        both = [p for p in pairs if p["A"] is not None and p["C"] is not None]
        agree = [p for p in both if p["agree"]]
        dis = [p for p in both if not p["agree"]]
        wrong_a = [p for p in pairs if p["A"] is not None and not p["A_ok"]]
        cost_a = sum(p["A_cost"] for p in pairs)
        cost_extra = sum(p["C_cost"] for p in missing)
        result["models"][m] = {
            "tasks": len(pairs),
            "single_run_correct": sum(p["A_ok"] for p in pairs),
            "rerun_if_missing": {
                "correct": sum(p["A_ok"] if p["A"] is not None else p["C_ok"] for p in pairs),
                "extra_runs": len(missing), "gained_tasks": gained, "lost_tasks": [],
                "cost_single_usd": round(cost_a, 4), "cost_extra_usd": round(cost_extra, 4),
                "note": "按構造不會少題（第一跑有答案就用第一跑），不是檢定、不報 p 值"},
            "either_run_correct": sum(1 for p in pairs if p["A_ok"] or p["C_ok"]),
            "both_answered": len(both),
            "agree": len(agree), "agree_both_correct": sum(1 for p in agree if p["A_ok"] and p["C_ok"]),
            "agree_both_wrong": sum(1 for p in agree if not p["A_ok"] and not p["C_ok"]),
            "disagree": len(dis), "disagree_one_correct": sum(1 for p in dis if p["A_ok"] != p["C_ok"]),
            "disagree_both_wrong": sum(1 for p in dis if not p["A_ok"] and not p["C_ok"]),
            "single_run_wrong_answers": len(wrong_a),
            "single_run_wrong_flagged_by_disagreement": sum(1 for p in wrong_a
                                                            if p["C"] is not None and not p["agree"]),
            "single_run_correct_flagged_by_disagreement": sum(
                1 for p in pairs if p["A"] is not None and p["A_ok"] and p["C"] is not None and not p["agree"]),
            "pairs": pairs,
        }
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    for m, v in result["models"].items():
        print(m, {k: v[k] for k in v if k != "pairs"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
