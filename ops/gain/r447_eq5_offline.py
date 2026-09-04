#!/usr/bin/env python3
"""R452：LCB2 上的等預算「閘門 vs 多數決」——從 r447 的 OFF5 呼叫紀錄離線重建，零 API。

判準先行：`DECISION_20260904_R452_LCB2_EQ5_OFFLINE_RECONSTRUCTION.md`（5be4a8c，
本檔之前 commit）。本檔只是把那份文件逐條編碼，窗口／分母／推翻條件都不在這裡發明。

估計量宣稱（§三，收官不准換詞彙）：
  「**給定同一組候選，哪一條選擇規則交付得多**」。**不**答「兩個各自獨立抽樣的系統誰贏」。
    規則 A（閘門）：按呼叫順序取第一個 `visible_ok` 的候選；五份全不過 ⇒ 拒交。
    規則 B（多數決）：OFF5 實跑的選擇，**直接讀 rows，不重建**（rng 平手抽籤無法離線重放）。
  兩條規則各花 5 通呼叫 ⇒ 恆等於等預算。

主判分母（§三，事前指定）：有完整 5 份候選的 OFF5 題目**全體**；拒交＝沒交付＝不算對。
`accepted` 子集的版本照算但**不是仲裁者**。

擋門（§四，兩型「安靜量不到」都要擋；判準不是 rc≠0）：
  E1 缺欄位 ⇒ BROKEN（不准當 False 算過去）
  E2 候選數不是 5 ⇒ BROKEN（失敗的請求不是候選；重試才是那一份）
  E3 候選順序與 rows 的 `involved` 不符 ⇒ BROKEN（順序錯會讓「第一個通過的」換人）
  E4 校準對不上 ⇒ BROKEN（真資料校準，不是合成夾具）
  E5 可校準題數 < 20 ⇒ UNCALIBRATED
  E6 rows 有題但 calls 裡找不到 ⇒ BROKEN
  E11 BROKEN 時不准吐 Δ

用法：
  python3 ops/gain/r447_eq5_offline.py --selftest
  python3 ops/gain/r447_eq5_offline.py --run runs/g_r447_conform_lcb2 --json out.json
"""
from __future__ import annotations
import argparse, ast, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.gain.gain_run import extract_code, load_tasks, meets_demand   # noqa: E402
from ops.gain.replay.paired_ci import diff_ci, n_needed                # noqa: E402
from ops.gain.power_paired import mde_at_n                             # noqa: E402

MUTANT = ""
LAST_FAILS: list[str] = []

K = 5            # arm_off5 / arm_conform 共用的 k 上限（gain_run.py:308,514）
MIN_CALIB = 20   # DECISION §五 W1
REQUIRED_ROW = ("task_id", "involved", "worker", "visible_ok", "meets_demand", "accepted")


def off5_candidates(calls: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """task_id -> 按 calls.jsonl 檔序排好的 (agent_id, 回應全文)。

    只收 `ok=True`：失敗的請求**不是**一份候選（`generate()` 把重試吞在裡面，
    一份候選可能對應兩行 log）。這條在 E2 有第二個目擊者（X9 突變體）。
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for c in calls:
        m = c.get("meta") or {}
        if c.get("role") != "gen" or m.get("arm") != "OFF5":
            continue
        if not c.get("ok") and MUTANT != "X9_include_failed_calls":
            continue
        out.setdefault(m["task_id"], []).append((c.get("agent_id"), c.get("response") or ""))
    return out


def reconstruct(rows, calls, tasks, *, vis=None, hid=None) -> dict:
    if vis is None:
        def vis(code, task):
            ok, _ = meets_demand(code, task["visible_check"]["code"],
                                 entry_point=task.get("entry_point"))
            return bool(ok)
    if hid is None:
        def hid(code, task):
            ok, _ = meets_demand(code, task["hidden_check"]["code"],
                                 entry_point=task.get("entry_point"))
            return bool(ok)

    by_task = {t["task_id"]: t for t in tasks}
    cands = off5_candidates(calls)
    broken: list[str] = []
    per: list[dict] = []
    calib_n = calib_ok = 0

    orows = [r for r in rows if r.get("arm") == "OFF5"]
    if not orows:
        broken.append("no_off5_rows")

    for r in orows:
        tid = r.get("task_id")
        miss = [k for k in REQUIRED_ROW if k not in r]
        if miss and MUTANT != "X10_ignore_missing_fields":
            broken.append(f"missing_fields:{tid}:{miss}")
            continue
        task = by_task.get(tid)
        if task is None:
            broken.append(f"task_not_in_bank:{tid}")
            continue
        cs = cands.get(tid)
        if cs is None:
            broken.append(f"task_not_in_calls:{tid}")
            continue
        if len(cs) != K and MUTANT != "X7_skip_candidate_count":
            broken.append(f"candidate_count_mismatch:{tid}:{len(cs)}!={K}")
            continue
        order = [a for a, _ in cs]
        involved = list(r.get("involved") or [])
        if order != involved and MUTANT != "X3_skip_order_check":
            broken.append(f"candidate_order_mismatch:{tid}:{order}!={involved}")
            continue

        codes = [extract_code(t) for _, t in cs]
        visf = [bool(vis(cd, task)) for cd in codes]
        hidf = [bool(hid(cd, task)) for cd in codes]

        # ── 規則 A：第一個可見通過的
        idx = next((i for i, v in enumerate(visf) if v), None)
        if MUTANT == "X1_gate_takes_last" and any(visf):
            idx = max(i for i, v in enumerate(visf) if v)
        a_deliver = idx is not None
        if MUTANT == "X2_gate_reject_counts_as_deliv" and not a_deliver:
            # 「拒交時退回最後一位」＝把 fallback 當成一次選擇（記憶鐵律：fallback 不是選擇）
            a_deliver, idx = True, K - 1
        a_ok = bool(a_deliver and hidf[idx])

        # ── 規則 B：實測，不重建
        b_ok = bool(r.get("accepted")) and bool(r.get("meets_demand"))
        if MUTANT == "X8_deliv_ignores_accepted":
            b_ok = bool(r.get("meets_demand"))

        # ── 真資料校準：`worker` 在 `involved` 裡唯一時，被選中的位置是唯一決定的
        if involved.count(r.get("worker")) == 1:
            ci = involved.index(r.get("worker"))
            calib_n += 1
            expect = (bool(r.get("visible_ok")), bool(r.get("meets_demand")))
            got = (visf[ci], hidf[ci])
            if MUTANT == "X4_skip_calibration":
                got = expect
            if got == expect:
                calib_ok += 1
            else:
                broken.append(f"calibration_mismatch:{tid}:rows={expect}:rebuilt={got}")

        per.append({"task_id": tid, "visible": visf, "hidden": hidf,
                    "gate_idx": idx, "gate_deliv": a_deliver, "gate_ok": a_ok,
                    "vote_ok": b_ok, "vote_accepted": bool(r.get("accepted"))})

    out: dict = {"broken": broken, "per_task": per,
                 "calibration": {"n": calib_n, "agree": calib_ok,
                                 "rate_pct": 100.0 * calib_ok / calib_n if calib_n else None,
                                 "min_required": MIN_CALIB}}
    if calib_n < MIN_CALIB and MUTANT != "X5_skip_min_calib":
        out["calibration"]["under_min"] = True

    n = len(per)
    b = sum(1 for p in per if p["gate_ok"] and not p["vote_ok"])
    c = sum(1 for p in per if p["vote_ok"] and not p["gate_ok"])
    gate_rej = sum(1 for p in per if not p["gate_deliv"])

    out["rule_rates"] = {
        "n_processed": n,
        "gate_deliv_correct": sum(1 for p in per if p["gate_ok"]),
        "vote_deliv_correct": sum(1 for p in per if p["vote_ok"]),
        "gate_reject_n": gate_rej,
        "gate_reject_pct": 100.0 * gate_rej / n if n else None,
        "gate_reject_window_W2": "2–14%（DECISION §五 W2）",
        "denominator": "processed（DECISION §三 事前指定的主判分母）",
    }
    # 次要分母：只看規則 A 有交付的那些題（**不是仲裁者**）
    sub = [p for p in per if p["gate_deliv"]]
    out["secondary_accepted_subset_NOT_ARBITER"] = {
        "n": len(sub),
        "gate_correct_pct": 100.0 * sum(1 for p in sub if p["gate_ok"]) / len(sub) if sub else None,
        "vote_correct_pct": 100.0 * sum(1 for p in sub if p["vote_ok"]) / len(sub) if sub else None,
    }

    # 探索性（非事前註冊）：任何選擇規則的天花板，以及閘門有沒有殺掉好答案
    oracle = sum(1 for p in per if any(p["hidden"]))
    killed = [p["task_id"] for p in per if not p["gate_deliv"] and any(p["hidden"])]
    out["exploratory"] = {
        "oracle_any_candidate_correct": oracle,
        "oracle_pct": 100.0 * oracle / n if n else None,
        "gate_rejected_but_some_candidate_correct": len(killed),
        "gate_rejected_but_some_candidate_correct_ids": killed,
        "candidates_visible_fail_hidden_ok": sum(
            1 for p in per for v, h in zip(p["visible"], p["hidden"]) if h and not v),
        "note": "非事前註冊、探索性；不改 R440Z 任何一條 P-Z 的判決。",
    }

    ok_to_report = not broken and not out["calibration"].get("under_min")
    if MUTANT == "X6_emit_delta_when_broken":
        ok_to_report = True
    if ok_to_report:
        r_ci = diff_ci(b, c, n) if n else None
        out["paired_gate_vs_vote"] = {
            "b_gate_only": b, "c_vote_only": c,
            "n_discordant": (r_ci or {}).get("n_discordant"),
            "delta_pp": 100.0 * (r_ci or {}).get("delta", 0.0),
            "ci_lo_pp": 100.0 * (r_ci or {}).get("lo", 0.0),
            "ci_hi_pp": 100.0 * (r_ci or {}).get("hi", 0.0),
            "p_mcnemar": (r_ci or {}).get("p_mcnemar"),
            "window_W3": "0 到 +12pp，方向為正；p 很可能 > 0.05（DECISION §五 W3）",
        }
        disc_rate = ((r_ci or {}).get("n_discordant") or 0) / n if n else 0.0
        out["power"] = {                      # DECISION §五 W4：CI 旁邊一定要有這兩個
            "mde_at_n_pp": mde_at_n(n, disc_rate)["mde_pp"],
            "n_disc_expected": mde_at_n(n, disc_rate)["n_disc_expected"],
            "n_needed_for_5pp": n_needed((r_ci or {}).get("n_discordant") or 0, n),
        }
    else:
        out["paired_gate_vs_vote"] = None
        out["power"] = None

    out["verdict"] = ("BROKEN" if broken else
                      "UNCALIBRATED" if out["calibration"].get("under_min") else
                      "RECONSTRUCTED")
    return out


# ─────────────────────────── 夾具 ───────────────────────────
# r699 教訓：夾具不共用被測檔的 helper、欄位字面字串在這裡重寫一次；
# r695 教訓：B 不從 A 導出——`vote_ok` 是夾具自己寫死的，跟 `visible/hidden` 無關。
def _fx(*, order_bad=False, count_bad=False, miss=False):
    """回傳 (rows, calls, tasks, vis, hid)。候選碼用標記字串，scorer 讀標記。"""
    def mk(tid, marks, involved, worker, row_vis, row_hid, accepted):
        row = {"arm": "OFF5", "task_id": tid, "involved": list(involved), "worker": worker,
               "visible_ok": row_vis, "meets_demand": row_hid, "accepted": accepted}
        if miss and tid == "t0":
            row.pop("visible_ok")
        cl = [{"role": "gen", "ok": True, "agent_id": a,
               "response": "```python\nMARK_" + m + "\n```", "meta": {"arm": "OFF5", "task_id": tid}}
              for a, m in zip(involved, marks)]
        return row, cl

    specs = [
        # tid  候選標記(V=可見過,H=hidden 對)          involved          chosen  rowvis rowhid acc
        ("t0", ["v0h0", "v1h1", "v1h0", "v0h1", "v0h0"], list("abcde"), "b", True,  True,  True),
        ("t1", ["v0h1", "v0h0", "v0h0", "v0h0", "v0h0"], list("fghij"), "f", False, True,  True),
        ("t2", ["v1h0", "v0h0", "v0h1", "v0h0", "v0h0"], list("klmno"), "m", False, True,  True),
        ("t3", ["v0h0", "v0h0", "v0h0", "v0h0", "v0h0"], list("pqrst"), "p", False, False, False),
        ("t4", ["v1h1", "v0h0", "v0h0", "v0h0", "v0h0"], list("uvwxy"), "v", False, False, True),
        # t5：`accepted=False ∧ meets_demand=True`。實跑的 OFF5 不產生這個形狀
        # （它從不拒交），但沒有它，`deliv = accepted ∧ meets_demand` 這個合取的
        # 前半在夾具上**結構性看不見**（X8 突變體會安靜通過＝空綠燈，r695 同型）。
        # `worker` 在 `involved` 裡出現兩次 ⇒ 被選中的位置不唯一 ⇒ 不進校準。
        ("t5", ["v1h1", "v0h0", "v0h0", "v0h0", "v0h0"], ["z", "z", "A", "B", "C"],
         "z", False, True, False),
    ]
    rows, calls = [], []
    for tid, marks, inv, w, rv, rh, ac in specs:
        r, cl = mk(tid, marks, inv, w, rv, rh, ac)
        rows.append(r)
        calls.extend(cl)
    if order_bad:                      # 只翻順序，不動任何別的量（r695：只翻其中一個）
        cs = [c for c in calls if c["meta"]["task_id"] == "t0"]
        cs[0]["agent_id"], cs[1]["agent_id"] = cs[1]["agent_id"], cs[0]["agent_id"]
    if count_bad:
        calls = [c for c in calls if not (c["meta"]["task_id"] == "t2" and c["agent_id"] == "o")]
    tasks = [{"task_id": t[0], "entry_point": "f",
              "visible_check": {"code": "V"}, "hidden_check": {"code": "H"}} for t in specs]

    def vis(code, task):
        return "v1" in code
    def hid(code, task):
        return "h1" in code
    return rows, calls, tasks, vis, hid


def _srcconst(name):
    """契約常數逐字從本檔原始碼取（r699：不從 import 拿，避免夾具與被測檔同源）。"""
    tree = ast.parse(pathlib.Path(__file__).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    return None


def selftest() -> int:
    fails: list[str] = []

    def ck(label, cond, extra=""):
        if not cond:
            fails.append(f"{label} {extra}")

    # ── 前置尺：夾具本身要成立（r699：不驗這個，夾具壞掉會長得像產品沒 bug）
    ck("P0 契約常數 K/MIN_CALIB 與 DECISION 一致",
       _srcconst("K") == 5 and _srcconst("MIN_CALIB") == 20,
       f"K={_srcconst('K')} MIN_CALIB={_srcconst('MIN_CALIB')}")
    ck("P1 extract_code 在夾具回應上吐得出標記",
       extract_code("```python\nMARK_v1h0\n```").strip() == "MARK_v1h0",
       repr(extract_code("```python\nMARK_v1h0\n```")))
    rows, calls, tasks, vis, hid = _fx()
    ck("P2 夾具的 vote_ok 不是從 visible/hidden 導出的",
       [r["meets_demand"] for r in rows] != [("h1" in m) for m in
                                             ["v0h0", "v0h1", "v1h0", "v0h0", "v1h1"]])

    res = reconstruct(rows, calls, tasks, vis=vis, hid=hid)
    per = {p["task_id"]: p for p in res["per_task"]}

    ck("E7 規則 A 取第一個可見通過的（t0 是 idx1 不是 idx2）",
       per.get("t0", {}).get("gate_idx") == 1, str(per.get("t0")))
    ck("E7b 規則 A 的正確與否讀那一位的 hidden（t2 gate_ok=False）",
       per.get("t2", {}).get("gate_ok") is False, str(per.get("t2")))
    ck("E8 五份全不過 ⇒ 拒交，不准 fallback 當交付（t3）",
       per.get("t3", {}).get("gate_deliv") is False and per.get("t3", {}).get("gate_ok") is False,
       str(per.get("t3")))
    ck("E9 規則 B 讀 rows 的 accepted∧meets_demand（t5 acc=False∧md=True ⇒ vote_ok=False）",
       per.get("t5", {}).get("vote_ok") is False and per.get("t1", {}).get("vote_ok") is True,
       f"t5={per.get('t5')} t1={per.get('t1')}")
    ck("E10 主判分母是 processed（拒交列仍在分母裡）",
       res["rule_rates"]["n_processed"] == 6 and res["rule_rates"]["gate_reject_n"] == 2,
       str(res["rule_rates"]))
    # b：只有閘門對 = t0(gate t0 idx1 h1 → True; vote True) …逐題手算
    #   t0 gate True  vote True  → concordant
    #   t1 gate 無人過→拒交 False vote True → c
    #   t2 gate idx0 h0 False     vote True → c
    #   t3 gate False             vote False→ concordant
    #   t4 gate idx0 h1 True      vote False→ b
    ck("E13 探索性天花板數對得上（t0,t1,t2,t4,t5 各有至少一份 hidden 對）",
       res["exploratory"]["oracle_any_candidate_correct"] == 5,
       str(res["exploratory"]))
    ck("E13b 閘門拒交卻有好答案的題目要點名（t1）",
       res["exploratory"]["gate_rejected_but_some_candidate_correct_ids"] == ["t1"],
       str(res["exploratory"]))
    ck("E5 UNCALIBRATED：可校準題數 5 < 20（t5 平手不進校準）",
       res["verdict"] == "UNCALIBRATED" and res["calibration"]["n"] == 5, str(res["calibration"]))
    ck("E11 UNCALIBRATED 時不吐 Δ／檢定力",
       res["paired_gate_vs_vote"] is None and res["power"] is None, str(res["verdict"]))

    # 校準真的會叫：把 t0 的 rows 值翻掉（只翻 rows，不動候選）
    rows2, calls2, tasks2, vis2, hid2 = _fx()
    rows2[0]["meets_demand"] = False        # t0 chosen=b=idx1 → hidden 應是 True
    res2 = reconstruct(rows2, calls2, tasks2, vis=vis2, hid=hid2)
    ck("E4 校準對不上 ⇒ BROKEN",
       res2["verdict"] == "BROKEN"
       and any(x.startswith("calibration_mismatch:t0") for x in res2["broken"]),
       str(res2["broken"]))

    rows3, calls3, tasks3, v3, h3 = _fx(order_bad=True)
    res3 = reconstruct(rows3, calls3, tasks3, vis=v3, hid=h3)
    ck("E3 候選順序與 involved 不符 ⇒ BROKEN",
       any(x.startswith("candidate_order_mismatch:t0") for x in res3["broken"]), str(res3["broken"]))

    rows4, calls4, tasks4, v4, h4 = _fx(count_bad=True)
    res4 = reconstruct(rows4, calls4, tasks4, vis=v4, hid=h4)
    ck("E2 候選數不是 5 ⇒ BROKEN",
       any(x.startswith("candidate_count_mismatch:t2") for x in res4["broken"]), str(res4["broken"]))

    rows5, calls5, tasks5, v5, h5 = _fx(miss=True)
    res5 = reconstruct(rows5, calls5, tasks5, vis=v5, hid=h5)
    ck("E1 缺欄位 ⇒ BROKEN",
       any(x.startswith("missing_fields:t0") for x in res5["broken"]), str(res5["broken"]))

    rows6, calls6, tasks6, v6, h6 = _fx()
    calls6 = [c for c in calls6 if c["meta"]["task_id"] != "t4"]
    res6 = reconstruct(rows6, calls6, tasks6, vis=v6, hid=h6)
    ck("E6 rows 有題但 calls 找不到 ⇒ BROKEN",
       any(x.startswith("task_not_in_calls:t4") for x in res6["broken"]), str(res6["broken"]))

    # 失敗的請求不是候選
    rows7, calls7, tasks7, v7, h7 = _fx()
    calls7.insert(1, {"role": "gen", "ok": False, "agent_id": "zz", "response": "",
                      "meta": {"arm": "OFF5", "task_id": "t0"}})
    res7 = reconstruct(rows7, calls7, tasks7, vis=v7, hid=h7)
    ck("E2b 失敗的請求不算候選（多一行 ok=False 不該改變任何東西）",
       not res7["broken"] and res7["per_task"] == res["per_task"], str(res7["broken"]))

    # 可校準題數 ≥ 20 時要能吐 Δ（否則 E5 會把所有真跑都擋掉＝空綠燈）
    big_rows, big_calls, big_tasks = [], [], []
    for i in range(22):
        r, cl = None, None
        rr, cc, tt, _, _ = _fx()
        for r0, t0 in zip(rr, tt):
            r0 = dict(r0); r0["task_id"] = f"{r0['task_id']}_{i}"
            t0 = dict(t0); t0["task_id"] = r0["task_id"]
            big_rows.append(r0); big_tasks.append(t0)
        for c0 in cc:
            c0 = json.loads(json.dumps(c0))
            c0["meta"]["task_id"] = f"{c0['meta']['task_id']}_{i}"
            big_calls.append(c0)
    resb = reconstruct(big_rows, big_calls, big_tasks, vis=vis, hid=hid)
    ck("E5b 可校準題數 ≥20 ⇒ RECONSTRUCTED 且吐得出 Δ 與檢定力",
       resb["verdict"] == "RECONSTRUCTED" and resb["paired_gate_vs_vote"] is not None
       and resb["power"]["mde_at_n_pp"] is not None,
       f"{resb['verdict']} calib={resb['calibration']['n']}")
    ck("E12 b/c 逐題手算對得上（每份夾具 b=2 c=2，×22）",
       resb["paired_gate_vs_vote"]["b_gate_only"] == 44
       and resb["paired_gate_vs_vote"]["c_vote_only"] == 44,
       str(resb["paired_gate_vs_vote"]))
    ck("E14 W2 拒交率照 processed 分母算（22×2 / 22×6 = 33.33%）",
       abs(resb["rule_rates"]["gate_reject_pct"] - 100.0 * 2 / 6) < 1e-9,
       str(resb["rule_rates"]["gate_reject_pct"]))

    LAST_FAILS[:] = fails
    for f in fails:
        print("  FAIL " + f)
    print(f"SELFTEST {'PASS' if not fails else 'FAIL'} ({len(fails)} failed) "
          f"MUTANT={MUTANT or 'none'}")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--bank", default="lcb2")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", default="g-r440-lcb2")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run 或 --selftest 擇一")
    d = pathlib.Path(a.run)
    rows = [json.loads(l) for l in (d / "rows.jsonl").read_text().splitlines() if l.strip()]
    calls = [json.loads(l) for l in (d / "calls.jsonl").read_text().splitlines() if l.strip()]
    tasks = load_tasks(bank=a.bank, n=a.n, seed=a.seed)
    res = reconstruct(rows, calls, tasks)
    import hashlib
    res["rows_lines"] = len(rows)
    res["rows_sha256_16"] = hashlib.sha256(
        (d / "rows.jsonl").read_bytes()).hexdigest()[:16]
    res["run"] = a.run
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if a.json:
        pathlib.Path(a.json).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
