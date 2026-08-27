#!/usr/bin/env python3
"""ON 臂的審查關卡拆解：評審票有沒有資訊量、關卡把多少訊號濾掉了。

為什麼要單獨一支：`summary.json` 只給 `reviewer_accuracy` 一個純量，而那個數字
在 round140 被發現**恰好等於 always-PASS 基線**（0.8137 vs 0.8137）——純量看不出
「這是常數函數」。準確率必須跟同一份票上的平庸基線並排才有意義。

兩層要分開報（`gain_run.py:477` `grounded_pass = raw_pass or not confirmed`）：
  raw_pass      評審自己說的（過關卡之前）
  grounded_pass 關卡放行之後、真正決定 `passed_review` 的那個

用法：
  python3 ops/gain/analyze_review_gate.py --run runs/<dir> [--json out.json]
"""
import argparse
import collections
import json
import pathlib


def load_on_rows(d: pathlib.Path) -> list[dict]:
    rows = []
    for line in (d / "rows.jsonl").open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("arm") == "ON":
            rows.append(r)
    return rows


def confusion(rows: list[dict], field: str) -> dict:
    """真值＝`initial_meets_demand`（評審看的是初稿，不能拿修訂後的結果幫它算對）。"""
    TP = FP = FN = TN = 0
    for r in rows:
        truth = r["initial_meets_demand"]
        for e in r["review_evidence"]:
            passed = e[field]
            if passed and truth:
                TP += 1
            elif passed and not truth:
                FP += 1
            elif (not passed) and truth:
                FN += 1
            else:
                TN += 1
    n = TP + FP + FN + TN
    if not n:
        return {"n": 0}
    always_pass = (TP + FN) / n
    return {
        "n": n,
        "fail_votes": FN + TN,
        "fail_vote_rate": (FN + TN) / n,
        "TP": TP, "FP": FP, "FN": FN, "TN": TN,
        "accuracy": (TP + TN) / n,
        "always_pass_baseline": always_pass,
        # 這一行才是重點：評審比「無腦全部放行」多帶了多少資訊
        "accuracy_minus_baseline": (TP + TN) / n - always_pass,
        "recall_on_wrong_drafts": TN / (TN + FP) if (TN + FP) else None,
        "precision_of_fail_votes": TN / (TN + FN) if (TN + FN) else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()
    rows = load_on_rows(pathlib.Path(args.run))
    if not rows:
        print("沒有 ON 列可分析")
        return 1

    raw = confusion(rows, "raw_pass")
    gnd = confusion(rows, "grounded_pass")
    status = collections.Counter(
        e["status"] for r in rows for e in r["review_evidence"])
    selected = collections.Counter(r["selected_version"] for r in rows)
    passed = collections.Counter(r["passed_review"] for r in rows)
    trans = collections.Counter(r["revision_transition"] for r in rows)
    improved = [
        {"task_id": r["task_id"], "passed_review": r["passed_review"],
         "selected_version": r["selected_version"]}
        for r in rows if r["revision_transition"] == "improved"
    ]

    for label, c in (("RAW 評審主張（關卡之前）", raw),
                     ("GROUNDED 生效票（決定 passed_review）", gnd)):
        print(f"--- {label} ---")
        print(f"  n={c['n']}  投 FAIL {c['fail_votes']} 票 ({100*c['fail_vote_rate']:.2f}%)")
        print(f"  TP={c['TP']} FP={c['FP']} FN={c['FN']} TN={c['TN']}")
        print(f"  accuracy={c['accuracy']:.4f}   always-PASS 基線={c['always_pass_baseline']:.4f}"
              f"   差={c['accuracy_minus_baseline']:+.4f}")
        if c["recall_on_wrong_drafts"] is not None:
            print(f"  抓到錯初稿 {100*c['recall_on_wrong_drafts']:.2f}%", end="")
        if c["precision_of_fail_votes"] is not None:
            print(f"   FAIL 票精確度 {100*c['precision_of_fail_votes']:.2f}%", end="")
        print()

    print(f"\nverify_review_counterexample status：{dict(status)}")
    print(f"selected_version：{dict(selected)}")
    print(f"passed_review：{ {str(k): v for k, v in passed.items()} }")
    print(f"revision_transition：{dict(trans)}")
    print(f"improved 的來源：{improved}")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({
            "run": args.run, "n_on_rows": len(rows),
            "raw": raw, "grounded": gnd,
            "status": dict(status), "selected_version": dict(selected),
            "passed_review": {str(k): v for k, v in passed.items()},
            "revision_transition": dict(trans), "improved_tasks": improved,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
