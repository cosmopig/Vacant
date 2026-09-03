#!/usr/bin/env python3
"""round661：量「把 infra_void 任務整筆丟出分母」對頭條 Δ 的影響上限。

為什麼要這支（判準全文 `runs/_analysis_r661/CRITERION.md`，先 commit 才開始量）：
  round660 的 N=844 頭條是 `set(ON_rows) & set(OFF5_rows)` 的交集。任一臂 void 的
  任務**整筆不在 rows.jsonl**，於是被安靜移出分母。S5 因此掉 50% 的任務、S6 掉 44%，
  兩層的 void 率都破了 LOOP_PROMPT E1 視窗規則第 4 點的 20% 上報門檻——而沒有被報。
  round660 只查過「row 在、但缺 meets_demand」那一類（六層皆 0），那是不同的一類。

方法（**新增估計量零、新增可調參數零**）：
  主格不動（丟掉＝SPEC 鐵律 2 的正解）。只是額外問：被丟掉的配對裡，**另一臂是知道的**，
  所以把未知那一臂填成對 ON 最壞／最好，就得到一個無假設的 Manski 型界。
  三個數字都直接呼叫 round656 已雙向驗證的 `paired_ci.diff_ci(b, c, n)`，只換 (b,c,n)。

  兩臂都缺 ⇒ **一律排除**。兩邊都沒資料，填任何值是捏造不是界。
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from ops.gain.replay.paired_ci import diff_ci                      # noqa: E402
from ops.gain.analyze_paired import arm_rows                        # noqa: E402

MUTANT = ""   # V1/V2/V3，只在 --selftest 內部設定


def bc_counts(A: dict, B: dict, n_tasks: int | None = None) -> dict:
    """A=ON、B=OFF5 的 task_id -> row。回傳三種填補下的 (b, c, n)。

    b = A 對而 B 錯（有利 ON）；c = B 對而 A 錯（有利 OFF5）。
    兩臂都缺的任務**不在 A 也不在 B**，所以分母只能由 union(A,B) 算，
    不能用 summary 的 tasks（那會把兩臂都缺的憑空塞進來）——突變體 V2 就是那個寫法。
    """
    ta, tb = set(A), set(B)
    both = sorted(ta & tb)
    only_a = sorted(ta - tb)          # OFF5 void：B 未知
    only_b = sorted(tb - ta)          # ON void：A 未知

    def ok(r):
        return bool(r.get("meets_demand"))

    b0 = sum(1 for t in both if ok(A[t]) and not ok(B[t]))
    c0 = sum(1 for t in both if ok(B[t]) and not ok(A[t]))
    n0 = len(both)
    rescued = len(only_a) + len(only_b)

    n_bound = n0 + rescued
    if MUTANT == "V2" and n_tasks is not None:   # 突變點：分母誤用 summary 的 tasks
        n_bound = n_tasks
    if MUTANT == "V3":                            # 突變點：忘記把救回的配對加進分母
        n_bound = n0

    # 最壞（對 ON）：A 未知填 False、B 未知填 True
    a_fill_worst = True if MUTANT == "V1" else False   # 突變點：方向填反
    bw = b0 + sum(1 for t in only_b if a_fill_worst and not ok(B[t]))
    cw = c0 + sum(1 for t in only_a if not ok(A[t]))          # B 填 True、A 錯 ⇒ c
    cw += sum(1 for t in only_b if ok(B[t]) and not a_fill_worst)

    # 最好（對 ON）：A 未知填 True、B 未知填 False
    bb = b0 + sum(1 for t in only_a if ok(A[t])) + sum(1 for t in only_b if not ok(B[t]))
    cb = c0

    # 各臂在兩種填補下的「成功數」——V1 的方向錯誤由這裡機械地抓到（見 selftest P-B1/P-B2）
    on_known = sum(1 for t in both if ok(A[t])) + sum(1 for t in only_a if ok(A[t]))
    off5_known = sum(1 for t in both if ok(B[t])) + sum(1 for t in only_b if ok(B[t]))
    on_ok_worst = on_known + (len(only_b) if a_fill_worst else 0)
    on_ok_best = on_known + len(only_b)
    off5_ok_worst = off5_known + len(only_a)
    off5_ok_best = off5_known

    return {
        "n_both": n0, "n_only_ON_row": len(only_a), "n_only_OFF5_row": len(only_b),
        "n_rescued": rescued,
        "on_known_ok": on_known, "off5_known_ok": off5_known,
        "on_ok_worst": on_ok_worst, "on_ok_best": on_ok_best,
        "off5_ok_worst": off5_ok_worst, "off5_ok_best": off5_ok_best,
        "drop": {"b": b0, "c": c0, "n": n0},
        "worst_for_ON": {"b": bw, "c": cw, "n": n_bound},
        "best_for_ON": {"b": bb, "c": cb, "n": n_bound},
    }


def ci(d: dict) -> dict:
    r = diff_ci(d["b"], d["c"], d["n"])
    return {"b": d["b"], "c": d["c"], "n": d["n"],
            "delta_pp": r["delta"] * 100, "lo_pp": r["lo"] * 100, "hi_pp": r["hi"] * 100}


def stratum(label: str, group: str, d: pathlib.Path, a_arm="ON", b_arm="OFF5") -> dict:
    rows = [json.loads(l) for l in (d / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    A, B = arm_rows(rows, a_arm), arm_rows(rows, b_arm)
    summ = json.load((d / "summary.json").open(encoding="utf-8"))
    arms = summ.get("arms", {})
    tasks = arms.get(a_arm, {}).get("tasks")
    k = bc_counts(A, B, n_tasks=tasks)
    # 推翻條件之二：summary 的 infra_void 與 rows 缺漏數對不對得起來，差額照實登
    void_a = arms.get(a_arm, {}).get("infra_void")
    void_b = arms.get(b_arm, {}).get("infra_void")
    miss_a = (tasks - len(A)) if tasks is not None else None
    miss_b = (tasks - len(B)) if tasks is not None else None
    both_missing = (tasks - k["n_both"] - k["n_rescued"]) if tasks is not None else None
    # void 落點是否難度中性：ON void 的那些任務上 OFF5 的成功率 vs OFF5 整體成功率
    only_b_ids = sorted(set(B) - set(A))
    off5_on_voided = (sum(1 for t in only_b_ids if B[t].get("meets_demand")) / len(only_b_ids)
                      if only_b_ids else None)
    off5_overall = (sum(1 for t in B if B[t].get("meets_demand")) / len(B)) if B else None
    return {
        "label": label, "group": group, "dir": str(d), "tasks": tasks,
        "summary_infra_void": {a_arm: void_a, b_arm: void_b},
        "rows_missing_vs_tasks": {a_arm: miss_a, b_arm: miss_b},
        "void_rate_pct": {a_arm: (100.0 * void_a / tasks) if (void_a is not None and tasks) else None,
                          b_arm: (100.0 * void_b / tasks) if (void_b is not None and tasks) else None},
        "n_both": k["n_both"], "n_rescued": k["n_rescued"], "n_both_missing": both_missing,
        "n_only_ON_row": k["n_only_ON_row"], "n_only_OFF5_row": k["n_only_OFF5_row"],
        "drop": ci(k["drop"]), "worst_for_ON": ci(k["worst_for_ON"]), "best_for_ON": ci(k["best_for_ON"]),
        "off5_rate_on_ON_voided": off5_on_voided, "off5_rate_overall": off5_overall,
        "off5_rate_gap_pp": ((off5_on_voided - off5_overall) * 100
                             if (off5_on_voided is not None and off5_overall is not None) else None),
        "rows_lines": sum(1 for _ in (d / "rows.jsonl").open(encoding="utf-8")),
        "rows_sha256_16": hashlib.sha256((d / "rows.jsonl").read_bytes()).hexdigest()[:16],
        "_raw": k,
    }


def pool(strata: list[dict], key: str) -> dict:
    return ci({"b": sum(s["_raw"][key]["b"] for s in strata),
               "c": sum(s["_raw"][key]["c"] for s in strata),
               "n": sum(s["_raw"][key]["n"] for s in strata)})


def _mk(ok_a: list, ok_b: list, ids_a: list, ids_b: list):
    A = {t: {"meets_demand": v} for t, v in zip(ids_a, ok_a)}
    B = {t: {"meets_demand": v} for t, v in zip(ids_b, ok_b)}
    return A, B


def selftest() -> int:
    """雙向驗證。

    ⚠ round661 造尺途中發現：判準 §五原本寫的 **P-B「界必須包住主格」不是定理**。
    主格 drop 的分母是 both、界的分母是 both+救回，兩者是**不同母體**；
    加大分母會把 |delta| 往 0 拉。反例（實跑）：drop=diff_ci(0,5,10)=−50.00pp、
    worst=diff_ci(0,5,15)=−33.33pp ⇒ worst > drop。
    **此修正發生在碰任何真實資料之前**（見 GAIN_STATE round661 §二），
    改成機械導出的 P-B1/P-B2：填補方向由「各臂成功數在最壞／最好下該是多少」定義。
    """
    global MUTANT
    fails = []

    def run(mut):
        global MUTANT
        MUTANT = mut
        out = {}
        ids = [f"t{i}" for i in range(20)]
        A, B = _mk([True] * 12 + [False] * 8, [True] * 8 + [False] * 12, ids, ids)
        out["novoid"] = bc_counts(A, B, n_tasks=20)
        ia = [f"t{i}" for i in range(10)] + ["x1", "x2"]        # x1,x2 只有 ON（OFF5 void）
        ib = [f"t{i}" for i in range(10)] + ["y1", "y2", "y3"]  # y1..y3 只有 OFF5（ON void）
        A, B = _mk([True] * 6 + [False] * 4 + [True, False],
                   [True] * 5 + [False] * 5 + [True, False, True], ia, ib)
        # 母體 tasks=17：both 10 + 單邊缺 5 + **兩臂都缺 2**（V2 就是把這 2 個塞進分母）
        out["mixed"] = bc_counts(A, B, n_tasks=17)
        MUTANT = ""
        return out

    def check(m, tag):
        bad = []
        nv, mx = m["novoid"], m["mixed"]
        # P-A：void 皆為 0 時三格逐位元相同
        if not (json.dumps(nv["drop"], sort_keys=True) == json.dumps(nv["worst_for_ON"], sort_keys=True)
                == json.dumps(nv["best_for_ON"], sort_keys=True)):
            bad.append("P-A")
        # P-B1：ON 未知在最壞下一個都不算對、在最好下全算對
        if not (mx["on_ok_worst"] == mx["on_known_ok"]
                and mx["on_ok_best"] == mx["on_known_ok"] + mx["n_only_OFF5_row"]):
            bad.append("P-B1")
        # P-B2：OFF5 未知在最壞下全算對、在最好下一個都不算對
        if not (mx["off5_ok_worst"] == mx["off5_known_ok"] + mx["n_only_ON_row"]
                and mx["off5_ok_best"] == mx["off5_known_ok"]):
            bad.append("P-B2")
        # P-B3：兩個界本身有序（同分母下 b_worst<=b_best 且 c_worst>=c_best）
        if not (ci(mx["worst_for_ON"])["delta_pp"] <= ci(mx["best_for_ON"])["delta_pp"]):
            bad.append("P-B3")
        # P-C：分母 = both + 單邊缺；兩臂都缺（此例 2 個）不得進 n
        if mx["worst_for_ON"]["n"] != mx["n_both"] + mx["n_rescued"]:
            bad.append("P-C")
        # P-D：兩個界同分母
        if mx["worst_for_ON"]["n"] != mx["best_for_ON"]["n"]:
            bad.append("P-D")
        print(f"=== {tag} === " + ("PASS" if not bad else "FAIL: " + ", ".join(bad)))
        return bad

    if check(run(""), "乾淨（必須 PASS）"):
        fails.append("乾淨版沒過")
    caught = {}
    for mut, want in (("V1", "P-B1"), ("V2", "P-C"), ("V3", "P-C/P-D")):
        bad = check(run(mut), f"突變體 {mut}（預期被 {want} 抓到）")
        caught[mut] = bad
        if not bad:
            fails.append(f"{mut}: 沒被任何命題抓到 ⇒ 工具沒牙齒")
        elif want.split("/")[0] not in bad:
            fails.append(f"{mut}: 被抓到了但不是事前指定的 {want}（實得 {bad}）")
    print(f"\nSELFTEST {'PASS' if not fails else 'FAIL'}  caught={json.dumps(caught)}")
    if fails:
        print("  " + "; ".join(fails))
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--stratum", action="append", default=[], help="LABEL:GROUP=dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    strata = []
    for spec in a.stratum:
        head, d = spec.split("=", 1)
        lab, grp = head.split(":", 1)
        strata.append(stratum(lab, grp, pathlib.Path(d)))
    groups = sorted({s["group"] for s in strata})
    out = {
        "strata": strata,
        "by_group": {g: {k: pool([s for s in strata if s["group"] == g], k)
                         for k in ("drop", "worst_for_ON", "best_for_ON")} for g in groups},
        "all": {k: pool(strata, k) for k in ("drop", "worst_for_ON", "best_for_ON")},
    }
    for s in strata:
        s.pop("_raw", None)
    txt = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True)
    if a.json:
        pathlib.Path(a.json).write_text(txt, encoding="utf-8")
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
