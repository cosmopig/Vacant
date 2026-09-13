#!/usr/bin/env python3
"""配對分析的下一層：discordant pair 具體是哪些題、贏在哪個機制環節。

為什麼要獨立成一支工具（round426）：
  analyze_paired.py 只出比例與 McNemar p 值。round413 起 discordant pair 數
  （只有 A 對 b / 只有 B 對 c）連續 13 輪完全沒變過，代表新增的配對題目全部
  兩臂一致，重跑同一支比例統計的邊際資訊量趨近零。要往下一層問「這 11 題
  具體是什麼、ON 的 review 鏈在贏／輸的題目上分別發生了什麼」，才可能有新
  發現——這支工具把 rows.jsonl 裡 ON 特有欄位（revision_transition／votes／
  reviewer 逐票）與 OFF5 特有欄位（vote_agreement／n_buckets／err）並排印出。

只做展示，不做判定——沒有新的統計檢定，只是把已經落盤的欄位挑出來對照。
"""
import argparse
import json
import pathlib


def load_rows(d: pathlib.Path) -> list[dict]:
    p = d / "rows.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def arm_rows(rows: list[dict], arm: str) -> dict[str, dict]:
    return {r["task_id"]: r for r in rows if r.get("arm") == arm}


def summarize_on(row: dict) -> str:
    votes = row.get("votes") or []
    vote_str = ",".join(f"{a}={v}" for a, v in votes)
    return (f"revision_transition={row.get('revision_transition')} "
            f"passed_review={row.get('passed_review')} votes=[{vote_str}]")


def summarize_off5(row: dict) -> str:
    return (f"vote_agreement={row.get('vote_agreement')} "
            f"n_buckets={row.get('n_buckets')} err={row.get('err') or '-'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run 目錄（ON/OFF5 須同一個 run）")
    ap.add_argument("--a-arm", default="ON")
    ap.add_argument("--b-arm", default="OFF5")
    args = ap.parse_args()

    d = pathlib.Path(args.run)
    rows = load_rows(d)
    A = arm_rows(rows, args.a_arm)
    B = arm_rows(rows, args.b_arm)
    common = sorted(set(A) & set(B))

    only_a = [t for t in common if A[t]["meets_demand"] and not B[t]["meets_demand"]]
    only_b = [t for t in common if B[t]["meets_demand"] and not A[t]["meets_demand"]]

    print(f"=== 只有 {args.a_arm} 對（{args.a_arm} 贏，n={len(only_a)}） ===")
    for t in only_a:
        print(t)
        print(f"  {args.a_arm}: {summarize_on(A[t]) if args.a_arm != 'OFF5' else summarize_off5(A[t])}")
        print(f"  {args.b_arm}: {summarize_off5(B[t]) if args.b_arm == 'OFF5' else summarize_on(B[t])}")

    print()
    print(f"=== 只有 {args.b_arm} 對（{args.b_arm} 贏，n={len(only_b)}） ===")
    for t in only_b:
        print(t)
        print(f"  {args.a_arm}: {summarize_on(A[t]) if args.a_arm != 'OFF5' else summarize_off5(A[t])}")
        print(f"  {args.b_arm}: {summarize_off5(B[t]) if args.b_arm == 'OFF5' else summarize_on(B[t])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
