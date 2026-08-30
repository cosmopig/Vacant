#!/usr/bin/env python3
"""round353 離線分析：CONCLUSION_20260830_G_EXPERIMENT.md 第97-101行點名的
「最關鍵、目前不存在的對照臂」——OFF5 + 同一道可見測試閘——其實不需要新開一個
實驗。round342 已經把 arm_off5() 的 visible_ok（behavior_signature 早就跑過
可見測資，零額外呼叫）寫進 rows.jsonl，只是沒有拿它改 accepted 語意。

本腳本純離線重算 OFF5 的「若改用這道免費閘門，會不會跟 accepted=True 一樣，
還是能把漏出量壓到跟 ON 一樣低」，跟 ON 的漏出量放在同一張表比較。
只讀 rows.jsonl，零新模型呼叫。

用法：python3 ops/gain/analyze_off5_gate_counterfactual.py [run_dir_name ...]
不給參數時用預設清單（所有 round342 之後、OFF5 rows 已有 visible_ok 欄位的 run）。
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = REPO_ROOT / "runs"

DEFAULT_RUNS = [
    "g_r342_3arm_20260830",
    "g_r345_3arm_20260830",
    "g_r348_3arm_20260830",  # round347 修 contract-dedent bug 之後（post_fix）
]


def load_rows(run):
    path = RUNS_DIR / run / "rows.jsonl"
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return None
    return [json.loads(l) for l in lines if l.strip()]


def leak_stats(rows, arm, accepted_key="accepted"):
    """accepted_key: 'accepted'（現行語意）或 callable(row)->bool（反事實）。"""
    sub = [r for r in rows if r.get("arm") == arm]
    if callable(accepted_key):
        acc = [r for r in sub if accepted_key(r)]
    else:
        acc = [r for r in sub if r.get(accepted_key)]
    n_acc = len(acc)
    n_leak = sum(1 for r in acc if not r.get("meets_demand"))
    rate = n_leak / n_acc if n_acc else float("nan")
    return n_acc, n_leak, rate, len(sub)


def main(run_names=None):
    runs = run_names or DEFAULT_RUNS

    pooled_off5_rows = []
    pooled_on_rows = []
    print("=== 逐 run（只算 OFF5 rows 已有 visible_ok 欄位的部分）===")
    for run in runs:
        rows = load_rows(run)
        if rows is None:
            print(f"  (skip {run}: no rows.jsonl)")
            continue
        off5_with_vok = [r for r in rows if r.get("arm") == "OFF5" and "visible_ok" in r]
        on_rows = [r for r in rows if r.get("arm") == "ON"]
        missing = sum(1 for r in rows if r.get("arm") == "OFF5") - len(off5_with_vok)
        print(f"  {run}: OFF5 有 visible_ok={len(off5_with_vok)}"
              f"（缺欄位跳過 {missing}）  ON={len(on_rows)}")
        pooled_off5_rows.extend(off5_with_vok)
        pooled_on_rows.extend(on_rows)
    print()

    all_rows = pooled_off5_rows + pooled_on_rows
    n = len(pooled_off5_rows)
    print(f"=== 合併後：OFF5(有 visible_ok) n={n}，ON n={len(pooled_on_rows)} ===")
    if n == 0:
        print("  樣本數為 0，無法計算。")
        return

    n_acc_real, n_leak_real, rate_real, n_sub = leak_stats(all_rows, "OFF5", "accepted")
    n_acc_cf, n_leak_cf, rate_cf, _ = leak_stats(
        all_rows, "OFF5", lambda r: r.get("visible_ok") is True)
    n_acc_on, n_leak_on, rate_on, n_sub_on = leak_stats(all_rows, "ON", "accepted")

    print(f"  OFF5 現行（accepted 恆 True）     n_accepted={n_acc_real}/{n_sub}  "
          f"漏出={n_leak_real}  漏出率={rate_real:.4f}" if n_acc_real else
          f"  OFF5 現行：n_accepted=0")
    print(f"  OFF5 反事實（accepted:=visible_ok）n_accepted={n_acc_cf}/{n_sub}  "
          f"漏出={n_leak_cf}  漏出率={rate_cf:.4f}" if n_acc_cf else
          f"  OFF5 反事實：n_accepted=0")
    print(f"  ON   現行                         n_accepted={n_acc_on}/{n_sub_on}  "
          f"漏出={n_leak_on}  漏出率={rate_on:.4f}" if n_acc_on else
          f"  ON：n_accepted=0")
    print()
    print("  判讀：反事實漏出率若接近 ON 的漏出率 ⇒ CONCLUSION 第97-101行的推翻條件"
          "觸發（Vacant 的機制在漏出量這件事上沒有超出免費閘門）。")
    print("  若反事實漏出率仍明顯高於 ON ⇒ 差額才是機制的真貢獻。")
    print("  ⚠ 目前 n 太小（round353 首次量測），只做管線驗證，不據此下結論。")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
