#!/usr/bin/env python3
"""round352 離線分析：評審與候選同模型家族 vs 不同家族，抓真失敗的準確率有沒有差。
只讀 rows.jsonl，零新模型呼叫。見 DECISION_20260830_R352_REVIEWER_FAMILY_BLINDSPOT.md。

用法：python3 ops/gain/analyze_reviewer_family.py [run_dir_name ...]
不給參數時用預設清單（round352 當時已完成的異質池 ON run）。
"""
import json
import sys
from pathlib import Path
from math import comb

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = REPO_ROOT / "runs"

VOID_GATE = 0.10  # SPEC_GAIN §7，與 analyze_fullbank_off.py／
                   # analyze_off5_gate_counterfactual.py 同一條規則（round357 補上）

DEFAULT_RUNS = [
    ("g_het3_r278_20260829", "pre_fix"),
    ("g_het2_r274_20260829", "pre_fix"),
    ("g_r342_3arm_20260830", "pre_fix"),
    ("g_r345_3arm_20260830", "pre_fix"),
    ("g_r348_3arm_20260830", "post_fix"),  # round347 修 contract-dedent bug 之後
    # ⚠ round356：g_r342/g_r345/g_r348 全部因 400-非重試 bug 被判定
    # void-gate-disqualified（DECISION_20260830_R356_HTTP400_RETRY_REVERSAL.md）。
]


def load_notes(run):
    path = RUNS_DIR / run / "notes.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def on_void_ratio(notes):
    n_void = sum(1 for nt in notes if nt.get("arm") == "ON" and "infra_void" in nt)
    return n_void  # 分母（n_measured）由呼叫端算，這裡只回傳分子避免重複讀 rows


def agent_model(agent_id):
    # gain_run.py:809 models[i % len(models)]，POOL 順序 careful-1,careful-2,
    # plain-1,plain-2,hasty-1,hasty-2 對應 i=0..5。這些 run 全部
    # --models qwen/...,gemma/...（qwen 排第一、gemma 排第二）⇒
    # agent_id 尾碼 "-1" 一律對到 qwen、"-2" 一律對到 gemma。
    # 對應規則本身用 reviewer_models 欄位逐票交叉驗證，見 main() 的 mismatch 計數。
    if agent_id.endswith("-1"):
        return "qwen"
    if agent_id.endswith("-2"):
        return "gemma"
    return "?"


def short_model(m):
    if not m:
        return "?"
    if "qwen" in m:
        return "qwen"
    if "gemma" in m:
        return "gemma"
    return m


def fisher_exact_one_sided(k_obs, K, n, N):
    """P(X<=k_obs) under Hypergeometric(N,K,n)，不用 scipy，純 math.comb。"""
    def pmf(k):
        if k < 0 or k > n or (K - k) < 0 or (K - k) > (N - n):
            return 0.0
        return comb(K, k) * comb(N - K, n - k) / comb(N, n)
    return sum(pmf(k) for k in range(0, k_obs + 1))


def main(run_names=None):
    runs = DEFAULT_RUNS if not run_names else [(r, "custom") for r in run_names]

    per_run = {}
    per_run_void = {}
    any_gate_exceeded = False
    mismatch = 0
    total_votes_checked = 0
    pooled = {}
    pooled_overall = {}

    for run, bucket in runs:
        pooled.setdefault(bucket, {"same": [0, 0], "diff": [0, 0]})
        pooled_overall.setdefault(bucket, {"same": [0, 0], "diff": [0, 0]})
        path = RUNS_DIR / run / "rows.jsonl"
        try:
            lines = path.read_text().splitlines()
        except FileNotFoundError:
            print(f"  (skip {run}: no rows.jsonl)")
            continue
        n_on_total = sum(1 for l in lines if l.strip() and json.loads(l).get("arm") == "ON")
        n_void = on_void_ratio(load_notes(run))
        ratio = n_void / (n_on_total + n_void) if (n_on_total + n_void) else 0.0
        gate_exceeded = ratio > VOID_GATE
        any_gate_exceeded = any_gate_exceeded or gate_exceeded
        per_run_void[run] = (n_on_total, n_void, ratio, gate_exceeded)
        n_rows = 0
        for line in lines:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("arm") != "ON":
                continue
            worker = d.get("worker")
            if not worker:
                continue
            gt = d.get("initial_meets_demand")
            if gt is None:
                continue
            cand_model = agent_model(worker)
            review_evidence = d.get("review_evidence") or []
            reviewer_models_field = d.get("reviewer_models") or []
            n_rows += 1
            for idx, ev in enumerate(review_evidence):
                aid = ev.get("agent_id")
                grounded_pass = ev.get("grounded_pass")
                if aid is None or grounded_pass is None:
                    continue
                derived_model = agent_model(aid)
                total_votes_checked += 1
                if idx < len(reviewer_models_field):
                    field_model = short_model(reviewer_models_field[idx])
                    if field_model != "?" and field_model != derived_model:
                        mismatch += 1
                key = "same" if derived_model == cand_model else "diff"
                pooled_overall[bucket][key][0] += 1
                if grounded_pass == gt:
                    pooled_overall[bucket][key][1] += 1
                if gt is False:
                    pooled[bucket][key][0] += 1
                    if grounded_pass is False:
                        pooled[bucket][key][1] += 1
        per_run[run] = n_rows

    print("=== 逐 run ON 列數（含 worker 與 initial_meets_demand 都非空）"
          "| void率 = infra_void/(ON rows+infra_void) ===")
    for r, n in per_run.items():
        n_on_total, n_void, ratio, gate_exceeded = per_run_void.get(r, (0, 0, 0.0, False))
        flag = "  ⚠ VOID-GATE-DISQUALIFIED" if gate_exceeded else ""
        print(f"  {r}: {n}  |  void率={ratio:.1%}({n_void}/{n_on_total + n_void}){flag}")
    print()
    print(f"=== 交叉驗證 i%2 推導 vs reviewer_models 欄位：{total_votes_checked} 票，"
          f"不一致 {mismatch} 票 ===")
    print()
    if any_gate_exceeded:
        print("  ⛔ 至少一個 run 的 ON 臂 void 率 > 10%（SPEC_GAIN §7 閘門）——下面每個"
              "  bucket 的準確率/p 值仍會印出，但屬於探索性數字，不得引用為結論性判讀"
              "（round357，見 DECISION_20260830_R356_HTTP400_RETRY_REVERSAL.md）。")
        print()

    for bucket, data in pooled_overall.items():
        print(f"--- {bucket} ---")
        n_same_fail, k_same_fail = pooled[bucket]["same"]
        n_diff_fail, k_diff_fail = pooled[bucket]["diff"]
        for key in ("same", "diff"):
            n_total, n_correct = data[key]
            acc = n_correct / n_total if n_total else float("nan")
            n_gt_false, n_caught = pooled[bucket][key]
            catch_rate = n_caught / n_gt_false if n_gt_false else float("nan")
            label = "同家族(reviewer==candidate)" if key == "same" else "不同家族"
            print(f"  {label}: 整體票準確率 {n_correct}/{n_total} = {acc:.4f}  |  "
                  f"真失敗題上抓到率 {n_caught}/{n_gt_false} = {catch_rate:.4f}")
        N = n_same_fail + n_diff_fail
        K = k_same_fail + k_diff_fail
        if N > 0 and 0 < K < N and n_same_fail > 0:
            p_one = fisher_exact_one_sided(k_same_fail, K, n_same_fail, N)
            print(f"  精確超幾何單尾 p（same-family 抓到數 <= 觀察值）= {p_one:.4f}")
        print()


if __name__ == "__main__":
    main(sys.argv[1:] or None)
