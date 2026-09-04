#!/usr/bin/env python3
"""把 CONFORM **被丟掉的候選**的 hidden 結果離線重建出來——零 API。

要補的洞（round701 發現，見 analyze_r447.py 的「歧義 3」）：
  `arm_conform` 拒交時只把**最後一位**候選送 hidden_check（gain_run.py:578），
  早停成功時也只有**通過可見閘門的那一位**被計分。所以 rows.jsonl 對
  「被可見閘門丟掉的那些候選到底對不對」是**結構性沉默**的。
  P-Z5 的第二子句（拒交題裡五份全錯 ≥80%）因此在 rows 上不可評估。

補救靠鐵律 3（全 I/O 落盤）：calls.jsonl 有每一通呼叫的回應全文，且每通 gen 都帶
`meta.arm` / `meta.task_id` ⇒ 可以把每題的 CONFORM 候選按檔序還原成 attempt 1..n，
用同一支 `meets_demand` 離線補算。零模型呼叫。

**這把尺自己要先在已知答案上校準**（記憶鐵律）：
  每題**最後一位**候選的 hidden 結果 rows.jsonl 已經記了（`meets_demand`）。
  重建值與它逐題比對——不一致就是重建錯了，一律 BROKEN，不准只報後面的數字。
  這是真資料校準，不是合成夾具。

輸出分兩層，**不准混在一起講**：
  (1) P-Z5b（事前註冊）：拒交題裡「五份全錯」的比例。
  (2) 候選層無損性（**非事前註冊、探索性**）：被可見閘門丟掉的候選裡，
      有幾個其實 hidden 是對的。P-Z6 的 rows 層版本看不到這些候選，
      而這正是 R440P §五 誠實邊界「拒交會殺掉好答案」講的那個風險。
      **它不改 P-Z6 的判決**，只照實記；要不要升格成判準是下一輪的事。

用法：
  python3 ops/gain/r447_reject_reconstruct.py --selftest
  python3 ops/gain/r447_reject_reconstruct.py --run runs/g_r447_conform_lcb2 --json out.json
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.gain.gain_run import extract_code, load_tasks, meets_demand  # noqa: E402

MUTANT = ""
LAST_FAILS: list[str] = []


def conform_candidates(calls: list[dict]) -> dict[str, list[str]]:
    """task_id -> 按 calls.jsonl 檔序排好的 CONFORM 候選回應全文。

    R457：**明確失敗（`ok is False`）的 gen 不是候選**，一律不收。
    理由是語意而非結果數字：失敗通的 `response` 是空字串，它不是模型交出來的候選。
    收了它只有兩種下場——(a) 撞上 `candidate_count_mismatch`（本輪 lcb_3762 就是），
    或 (b) 數量剛好對得上時，混進一個空字串候選、被 scorer 判為錯
    ⇒ **`all_candidates_wrong` 被灌水、P-Z5b 的分子直接偏高**。
    (b) 才是非修不可的理由：那會污染頭條數字，與綠不綠燈無關。
    `ok` 不存在視為成功（夾具不寫 `ok`；真 runner 每通都寫）。
    """
    out: dict[str, list[str]] = {}
    dropped = 0
    for c in calls:
        m = c.get("meta") or {}
        if c.get("role") != "gen" or m.get("arm") != "CONFORM":
            continue
        if c.get("ok") is False and MUTANT != "M4_count_failed_calls_as_candidates":
            dropped += 1
            continue
        out.setdefault(m["task_id"], []).append(c.get("response") or "")
    conform_candidates.last_dropped = dropped        # 只給呼叫端記帳用，不參與判斷
    return out


def reconstruct(rows, calls, tasks, *, scorer=None) -> dict:
    """scorer(code, task) -> bool；預設用 gain_run 的 meets_demand（同一條路徑）。"""
    if scorer is None:
        def scorer(code, task):
            ok, _ = meets_demand(code, task["hidden_check"]["code"],
                                 entry_point=task.get("entry_point"))
            return bool(ok)
    by_task = {t["task_id"]: t for t in tasks}
    cands = conform_candidates(calls)
    out: dict = {"broken": [], "per_task": [],
                 "dropped_failed_gen_calls": getattr(conform_candidates, "last_dropped", 0)}

    crows = [r for r in rows if r.get("arm") == "CONFORM"]
    if not crows:
        out["broken"].append("no_conform_rows")

    calib_n = calib_ok = 0
    disc_total = disc_hidden_ok = 0          # 被丟掉的候選：總數 / 其實是對的
    rej_tasks = rej_all_wrong = 0
    for r in crows:
        tid = r.get("task_id")
        task = by_task.get(tid)
        texts = cands.get(tid, [])
        if task is None:
            out["broken"].append(f"task_not_in_bank:{tid}")
            continue
        if len(texts) != r.get("conform_calls"):
            out["broken"].append(
                f"candidate_count_mismatch:{tid}:{len(texts)}!={r.get('conform_calls')}")
            continue
        attempts = r.get("conform_attempts") or []
        if len(attempts) != len(texts):
            out["broken"].append(f"attempts_len_mismatch:{tid}")
            continue
        hid = [scorer(extract_code(t), task) for t in texts]

        # ── 校準：最後一位候選的 hidden 結果 rows 已經記了
        calib_n += 1
        expect = bool(r.get("meets_demand"))
        got = bool(hid[-1]) if hid else False
        if MUTANT == "M1_skip_calibration":
            got = expect
        if got == expect:
            calib_ok += 1
        else:
            out["broken"].append(f"calibration_mismatch:{tid}:rows={expect}:rebuilt={got}")

        # ── 被可見閘門丟掉的候選（早停成功時前 n-1 位、拒交時全部）
        for a, h in zip(attempts, hid):
            if a.get("visible_ok") and MUTANT != "M3_count_all_candidates":
                continue
            disc_total += 1
            if h:
                disc_hidden_ok += 1

        if not r.get("accepted"):
            rej_tasks += 1
            if not any(hid):
                rej_all_wrong += 1
        out["per_task"].append({"task_id": tid, "accepted": bool(r.get("accepted")),
                                "n_cand": len(hid), "hidden": hid,
                                "visible": [bool(a.get("visible_ok")) for a in attempts]})

    # 這裡**沒有**再補一條「calib_ok != calib_n ⇒ BROKEN」的聚合擋門：
    # 只要有一題對不上，上面的 else 分支就已經 append 了 calibration_mismatch。
    # 聚合擋門與它逐字同義 ⇒ 沒有任何夾具分得出兩者 ⇒ 那是看不見的擋門（r695 教訓），
    # 不留。
    out["calibration"] = {"n": calib_n, "agree": calib_ok,
                          "rate_pct": 100.0 * calib_ok / calib_n if calib_n else None}

    # (1) 事前註冊的 P-Z5b
    out["pz5b"] = {"rejected_tasks": rej_tasks, "all_candidates_wrong": rej_all_wrong,
                   "pct": 100.0 * rej_all_wrong / rej_tasks if rej_tasks else None,
                   "window": "≥80%（DECISION §三 P-Z5 第二子句）"}
    # (2) 探索性：候選層無損性
    out["candidate_losslessness_EXPLORATORY"] = {
        "discarded_candidates": disc_total,
        "discarded_but_hidden_ok": disc_hidden_ok,
        "pct": 100.0 * disc_hidden_ok / disc_total if disc_total else None,
        "note": ("非事前註冊。P-Z6 是 rows 層、看不到被丟掉的候選；本項不改 P-Z6 判決，"
                 "要不要升格成判準是下一輪的事。>0 ⇒ 可見閘門在 LCB 上真的殺過好答案。"),
    }
    out["verdict"] = "BROKEN" if out["broken"] else "RECONSTRUCTED"
    return out


# ── 夾具：不共用上面任何 helper 的欄位定義，字面字串在這裡重寫一次
def _fx():
    tasks = [{"task_id": f"lcb_f{i}", "entry_point": "f",
              "hidden_check": {"code": "HIDDEN"}} for i in range(3)]
    rows = [
        # 早停成功：3 個候選，前 2 個可見沒過（其中 1 個 hidden 其實是對的 ⇒ 殺好答案）
        {"arm": "CONFORM", "task_id": "lcb_f0", "accepted": True, "meets_demand": True,
         "conform_calls": 3, "conform_attempts": [{"visible_ok": False}, {"visible_ok": False},
                                                  {"visible_ok": True}]},
        # 拒交：2 個候選全錯
        {"arm": "CONFORM", "task_id": "lcb_f1", "accepted": False, "meets_demand": False,
         "conform_calls": 2, "conform_attempts": [{"visible_ok": False}, {"visible_ok": False}]},
        # 拒交：2 個候選，最後一個 hidden 其實對 ⇒ 不算「五份全錯」
        {"arm": "CONFORM", "task_id": "lcb_f2", "accepted": False, "meets_demand": True,
         "conform_calls": 2, "conform_attempts": [{"visible_ok": False}, {"visible_ok": False}]},
    ]
    truth = {("lcb_f0", 0): False, ("lcb_f0", 1): True, ("lcb_f0", 2): True,
             ("lcb_f1", 0): False, ("lcb_f1", 1): False,
             ("lcb_f2", 0): False, ("lcb_f2", 1): True}
    calls = []
    for tid, n in (("lcb_f0", 3), ("lcb_f1", 2), ("lcb_f2", 2)):
        for j in range(n):
            calls.append({"role": "gen", "meta": {"arm": "CONFORM", "task_id": tid},
                          "response": f"```python\n# {tid}:{j}\n```"})
    def scorer(code, task):
        for (tid, j), v in truth.items():
            if f"# {tid}:{j}" in code:
                return v
        raise AssertionError("夾具的 scorer 對不到候選")
    return rows, calls, tasks, scorer


def selftest() -> int:
    global MUTANT, LAST_FAILS
    fails: list[str] = []
    LAST_FAILS = fails

    def ck(label, cond, extra=""):
        print(f"  {'ok  ' if cond else 'FAIL'} {label} {extra}")
        if not cond:
            fails.append(label)

    rows, calls, tasks, sc = _fx()
    o = reconstruct(rows, calls, tasks, scorer=sc)
    ck("R0 乾淨夾具 RECONSTRUCTED", o["verdict"] == "RECONSTRUCTED", str(o["broken"]))
    ck("R1 校準 3/3（最後一位候選對得上 rows）", o["calibration"] == {"n": 3, "agree": 3, "rate_pct": 100.0},
       str(o["calibration"]))
    ck("R2 P-Z5b 分母只算拒交題", o["pz5b"]["rejected_tasks"] == 2, str(o["pz5b"]))
    ck("R3 P-Z5b 分子＝候選全錯的拒交題", o["pz5b"]["all_candidates_wrong"] == 1)
    ck("R4 P-Z5b 比例 50%", abs(o["pz5b"]["pct"] - 50.0) < 1e-9)
    cl = o["candidate_losslessness_EXPLORATORY"]
    ck("R5 被丟掉的候選數＝可見沒過的候選數", cl["discarded_candidates"] == 6, str(cl))
    ck("R6 抓到『丟掉但 hidden 其實對』", cl["discarded_but_hidden_ok"] == 2, str(cl))

    # 校準失敗 ⇒ BROKEN（不准只報後面的數字）
    r2 = [dict(x) for x in rows]; r2[1]["meets_demand"] = True
    o2 = reconstruct(r2, calls, tasks, scorer=sc)
    ck("R7 校準對不上 ⇒ BROKEN", o2["verdict"] == "BROKEN"
       and any(x.startswith("calibration_mismatch") for x in o2["broken"]), str(o2["broken"]))
    ck("R7b 校準比例照實回報", o2["calibration"]["agree"] == 2 and o2["calibration"]["n"] == 3,
       str(o2["calibration"]))

    # 候選數對不上 ⇒ BROKEN（安靜少一個候選＝安靜量不到）
    c3 = [x for x in calls if not (x["meta"]["task_id"] == "lcb_f0" and "0" in x["response"])]
    o3 = reconstruct(rows, c3, tasks, scorer=sc)
    ck("R8 候選數對不上 ⇒ BROKEN", o3["verdict"] == "BROKEN"
       and any(x.startswith("candidate_count_mismatch") for x in o3["broken"]), str(o3["broken"]))

    # 題目不在題庫 ⇒ BROKEN
    o4 = reconstruct(rows, calls, tasks[:2], scorer=sc)
    ck("R9 題目不在題庫 ⇒ BROKEN", o4["verdict"] == "BROKEN"
       and any(x.startswith("task_not_in_bank") for x in o4["broken"]))

    # 0 列 ⇒ BROKEN 不是 PASS
    ck("R10 0 列 CONFORM ⇒ BROKEN", reconstruct([], calls, tasks, scorer=sc)["verdict"] == "BROKEN")

    # 沒有拒交題時 pz5b 是 None，不准變成 100%
    r5 = [dict(rows[0])]
    o5 = reconstruct(r5, calls, tasks, scorer=sc)
    ck("R11 沒有拒交題 ⇒ pz5b.pct 是 None 不是 100", o5["pz5b"]["pct"] is None, str(o5["pz5b"]))

    # ── R457：失敗的 gen 不是候選
    # R12 多一通 ok=False ⇒ 候選數不變、判決不變、丟棄數記帳
    cf = list(calls) + [{"role": "gen", "ok": False, "error": "TimeoutError: timed out",
                         "response": "", "meta": {"arm": "CONFORM", "task_id": "lcb_f0"}}]
    o6 = reconstruct(rows, cf, tasks, scorer=sc)
    ck("R12 多一通失敗的 gen ⇒ 不算候選、判決與乾淨夾具相同",
       o6["verdict"] == o["verdict"] and not any(
           x.startswith("candidate_count_mismatch") for x in o6["broken"])
       and o6["dropped_failed_gen_calls"] == 1,
       f"verdict={o6['verdict']} dropped={o6['dropped_failed_gen_calls']} broken={o6['broken']}")

    # R13 幽靈候選：少一通成功 ＋ 多一通失敗 ⇒ 物理數量巧合對上。
    #     收失敗通的舊寫法會**安靜**混進一個空字串候選（被判為錯 ⇒ 灌水
    #     all_candidates_wrong ⇒ P-Z5b 分子偏高）；正確行為是候選數對不上 ⇒ BROKEN。
    # ⚠ 這裡**只准拿掉一通**。用 `"0" in response` 篩會連 task_id 裡的 "0" 一起匹配
    #   （lcb_f0 三通全中 ⇒ 0!=3），那樣 M4 底下數量一樣對不上＝這條測試沒有牙齒。
    _f0 = [i for i, x in enumerate(calls)
           if x["meta"]["task_id"] == "lcb_f0" and x["meta"]["arm"] == "CONFORM"]
    assert len(_f0) == 3, f"夾具前提變了：lcb_f0 有 {len(_f0)} 通"
    c7 = [x for i, x in enumerate(calls) if i != _f0[-1]]
    c7 = c7 + [{"role": "gen", "ok": False, "error": "TimeoutError: timed out",
                "response": "", "meta": {"arm": "CONFORM", "task_id": "lcb_f0"}}]
    # 夾具的 `sc` 對不到候選就 raise ⇒ M4 底下會**crash 收場**（crash 不算偵測到）。
    # 這裡用一層「空碼一律判錯」的包裝，讓 M4 底下走完流程、由判準本身吐 FAIL。
    def _sc_empty_ok(code, task):
        return False if not (code or "").strip() else sc(code, task)
    o7 = reconstruct(rows, c7, tasks, scorer=_sc_empty_ok)
    ck("R13 少一成功＋多一失敗 ⇒ BROKEN（不准用空字串幽靈候選補位）",
       o7["verdict"] == "BROKEN"
       and any(x.startswith("candidate_count_mismatch") for x in o7["broken"]),
       str(o7["broken"]))

    print(f"SELFTEST {'PASS' if not fails else 'FAIL'} ({len(fails)} failed) MUTANT={MUTANT or 'none'}")
    return 1 if fails else 0


def main() -> int:
    global MUTANT
    import os
    MUTANT = os.environ.get("MUTANT", "")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run 或 --selftest 二選一")
    d = pathlib.Path(a.run)
    raw = (d / "rows.jsonl").read_bytes()
    rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    calls = [json.loads(l) for l in (d / "calls.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    tasks = load_tasks("lcb2", summary["seed"], summary["n"], offset=summary.get("offset", 0))
    out = reconstruct(rows, calls, tasks)
    out["rows_lines"] = len(rows)
    out["rows_sha256_16"] = hashlib.sha256(raw).hexdigest()[:16]
    out["run"] = str(d)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str),
                                        encoding="utf-8")
    return 0 if out["verdict"] == "RECONSTRUCTED" else 1


if __name__ == "__main__":
    sys.exit(main())
