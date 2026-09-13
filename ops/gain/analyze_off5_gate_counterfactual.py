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

VOID_GATE = 0.10  # SPEC_GAIN §7，與 analyze_fullbank_off.py 同一條規則

DEFAULT_RUNS = [
    "g_r342_3arm_20260830",
    "g_r345_3arm_20260830",
    "g_r348_3arm_20260830",  # round347 修 contract-dedent bug 之後（post_fix）
    # ⚠ round356：這三個 run 全部因 400-非重試 bug 被判定 void-gate-disqualified
    # （見 DECISION_20260830_R356_HTTP400_RETRY_REVIEW.md）。留在清單裡是為了讓
    # void-gate 斷言能印出「這些 run 為什麼不能下結論」，不是因為它們的數字可信。
]


def load_rows(run):
    path = RUNS_DIR / run / "rows.jsonl"
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return None
    return [json.loads(l) for l in lines if l.strip()]


def load_notes(run):
    path = RUNS_DIR / run / "notes.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def arm_void_ratio(rows, notes, arm):
    """round356 補的欠款：逐 run 逐臂算 void 率，比對 SPEC_GAIN §7 的 10% 閘門。"""
    n_measured = sum(1 for r in rows if r.get("arm") == arm)
    n_void = sum(1 for nt in notes if nt.get("arm") == arm and "infra_void" in nt)
    total = n_measured + n_void
    ratio = (n_void / total) if total else 0.0
    return {"n_measured": n_measured, "n_void": n_void, "ratio": ratio,
            "gate_exceeded": ratio > VOID_GATE}


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
    any_gate_exceeded = False
    print("=== 逐 run（只算 OFF5 rows 已有 visible_ok 欄位的部分）===")
    for run in runs:
        rows = load_rows(run)
        if rows is None:
            print(f"  (skip {run}: no rows.jsonl)")
            continue
        notes = load_notes(run)
        off5_with_vok = [r for r in rows if r.get("arm") == "OFF5" and "visible_ok" in r]
        on_rows = [r for r in rows if r.get("arm") == "ON"]
        missing = sum(1 for r in rows if r.get("arm") == "OFF5") - len(off5_with_vok)
        v_off5 = arm_void_ratio(rows, notes, "OFF5")
        v_on = arm_void_ratio(rows, notes, "ON")
        gate_flag = ""
        if v_off5["gate_exceeded"] or v_on["gate_exceeded"]:
            any_gate_exceeded = True
            gate_flag = "  ⚠ VOID-GATE-DISQUALIFIED"
        print(f"  {run}: OFF5 有 visible_ok={len(off5_with_vok)}"
              f"（缺欄位跳過 {missing}）  ON={len(on_rows)}"
              f"  |  void率 OFF5={v_off5['ratio']:.1%}({v_off5['n_void']}/"
              f"{v_off5['n_measured']+v_off5['n_void']}) "
              f"ON={v_on['ratio']:.1%}({v_on['n_void']}/{v_on['n_measured']+v_on['n_void']})"
              f"{gate_flag}")
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
    if any_gate_exceeded:
        print("  ⛔ BROKEN：至少一個 run 的至少一臂 void 率 > 10%（SPEC_GAIN §7 閘門）"
              "——上面印的漏出率數字只做管線/格式驗證，不得引用為結論性判讀"
              "（round356：round353/355 曾經誤用「n 太小」的措辭掩蓋這件事，"
              "見 DECISION_20260830_R356_HTTP400_RETRY_REVERSAL.md）。")
    else:
        print("  判讀：反事實漏出率若接近 ON 的漏出率 ⇒ CONCLUSION 第97-101行的推翻條件"
              "觸發（Vacant 的機制在漏出量這件事上沒有超出免費閘門）。")
        print("  若反事實漏出率仍明顯高於 ON ⇒ 差額才是機制的真貢獻。")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
