#!/usr/bin/env python3
"""calls_audit.py —— 呼叫帳目對帳尺（round704）

回答一個純 infra 的問題：**`calls_used` 到底在數什麼？**

round704 在 r447 抓到兩通 `ok:False` 的 gen 呼叫（皆 OFF5、皆第二次嘗試成功）。
追進 `gain_run.py` 後確認：每一處 `calls[0] += 1` 都在 `agent.generate()` **回傳之後**，
而 `generate()` 自己把 HTTP 重試吞在裡面 ⇒ **`calls_used` 數的是「邏輯呼叫」，
不是「HTTP 請求數」。** 重試在成本面是免費的。

這對三條臂是同一把尺（每臂都數 generate()），所以**不影響等預算比較**；
但它代表收官報告若寫「OFF5 用了 N 次 API 呼叫」會少算重試。這支尺把那個差額
變成一個**恆等式**，任何一邊漂掉都會被抓到：

    logged_attempts − Σ calls_used == retry_attempts

（只取「rows 已經寫下」的 (arm, task_id) 格；run 活著時 calls 會領先 rows，
那是正常的，不是帳對不上。）

判準（事前寫死）:
  ACCOUNTING_CONSISTENT  恆等式成立，且逐格皆成立
  ACCOUNTING_MISMATCH    恆等式不成立 ⇒ 有帳沒對上，列出逐格殘差
  BROKEN                 量不到（schema 漂掉／配對數塌下來）⇒ 不准當 PASS

**兩型「安靜量不到」都要擋**（r154 教訓）:
  1. schema 漂掉：calls 的 meta 缺 arm／task_id ⇒ 那些通會被安靜漏掉 ⇒ BROKEN
  2. 量到的數量塌下來：配對格數 < MIN_PAIRS ⇒ BROKEN

**欄位白名單**：本尺只讀 infra 欄位，結構上碰不到任何結果欄位
（meets_demand／accepted／visible_ok 一律不讀），所以期中跑它不構成序貫決策污染。

⚠ round705 抓到的量具假影（P-R447-AUDIT-1，本輪修）：`error` 原本不在白名單上，
被 `main()` 在進 `audit()` 之前剝掉 ⇒ `reason_recorded` 恆為 False ⇒ 本尺把
「**讀不到**失敗原因」報成「失敗原因**沒落盤**」。r447 的原始 `calls.jsonl` 兩通
失敗都寫了 `error`（brain_cline.py:181-207 保證），是本尺自己看不見。
`error` 是 infra 字串（例外類別＋HTTP body），不是結果欄位，加進白名單不影響 F8。
"""
from __future__ import annotations
import argparse, collections, hashlib, json, os, pathlib, sys

MUTANT = ""

# 只讀這些。結果欄位（meets_demand/accepted/visible_ok/...）刻意不在名單上。
CALL_FIELDS = frozenset({"ts_ms", "role", "attempt", "ok", "timeout_s",
                         "latency_ms", "meta", "error"})
ROW_FIELDS = frozenset({"arm", "task_id", "calls_used"})
BANNED_ROW_FIELDS = frozenset({"meets_demand", "accepted", "visible_ok",
                               "conform_attempts", "receipt_head"})
MIN_PAIRS = 10          # 少於這個數就不是「乾淨」，是「沒量到」

# 事前沒預期到、r447 實跑冒出來的一類：`role="preflight"` 的端點連通性探針。
# 它**在結構上**沒有 arm——`gain_run.py:1350-1356` 在進入任何臂之前就建了
# `ClineBrain("preflight", ...)`，meta 只有 model。所以它「沒有標籤」不是 schema
# 漂掉，是它本來就不屬於任何一格。
#
# ⚠ 這個豁免的方向對本尺**有利**（讓 BROKEN 更難觸發），所以理由只准是語意的：
# 上面那個行號是從 gain_run.py 原始碼逐字確認的，不是因為它害本尺變紅。
# 舊的量無條件保留在輸出（`untagged_calls_incl_nonexperimental`），
# 後輪要收回仲裁權隨時可以。名單外的任何 role 沒標籤，一律照舊 BROKEN。
NON_EXPERIMENTAL_ROLES = frozenset({"preflight"})


def _project_call(c: dict) -> dict:
    """白名單投影。**唯一的一份**——`main()` 與 selftest 夾具都得走這裡，
    否則夾具驗的是「原始 calls」而真資料進 audit() 前已被投影過，
    投影本身的缺陷（正是 P-R447-AUDIT-1 那個）結構上沒有夾具看得見（r699）。

    `response` 刻意**不**進白名單：它是模型輸出＝結果內容，整包帶進來會讓
    「期中跑它不構成序貫決策污染」失效。但「失敗通有沒有留下回應」仍要答 ⇒
    只帶一個 bool（`has_response`），不帶內容。
    """
    p = {k: v for k, v in c.items() if k in CALL_FIELDS}
    if MUTANT == "whitelist_strips_error":          # M6：r447 真的發生過的那個缺陷
        p.pop("error", None)
    if MUTANT == "whitelist_strips_response_flag":  # M7：把第二個子句弄死
        return p
    p["has_response"] = c.get("response") is not None
    return p


def _key(meta: dict) -> tuple | None:
    """calls 的配對鍵。meta 缺任一半就回 None——由呼叫端算成 untagged，不准安靜丟。"""
    if not isinstance(meta, dict):
        return None
    a, t = meta.get("arm"), meta.get("task_id")
    if MUTANT == "key_ignores_arm":       # M4：鍵少一半 ⇒ 配對塌掉
        return (t,) if t else None
    if a is None or t is None:
        if MUTANT == "silently_drop_untagged":   # M3：安靜漏掉沒標籤的通
            return ("__dropped__", "__dropped__")
        return None
    return (a, t)


def audit(rows: list[dict], calls: list[dict]) -> dict:
    # 白名單不在這裡自律（那會是死碼）——main() 在送進來之前就結構性地投影過了。
    # audit() 本體只碰 arm/task_id/calls_used，F8 用「有沒有結果欄位輸出一模一樣」證明。
    used = {}
    for r in rows:
        a, t = r.get("arm"), r.get("task_id")
        if a is None or t is None:
            continue
        used[(a, t)] = r.get("calls_used")

    logged = collections.Counter()
    retries = collections.Counter()
    untagged = 0                 # 只數「該有標籤卻沒有」的
    untagged_all = 0             # 舊語意：所有沒標籤的，無條件保留
    nonexp = collections.Counter()
    fails = []
    for c in calls:
        k = _key(c.get("meta") or {})
        if k is None:
            untagged_all += 1
            role = c.get("role")
            if role in NON_EXPERIMENTAL_ROLES and MUTANT != "no_role_exemption":
                nonexp[role] += 1
            else:
                untagged += 1
            continue
        logged[k] += 1
        att = c.get("attempt") or 1
        is_retry = att > 1
        if MUTANT == "retry_off_by_one":   # M2：把每一通都算成重試
            is_retry = att >= 1
        if is_retry:
            retries[k] += 1
        if c.get("ok") is False:
            fails.append({"arm": k[0] if len(k) > 1 else None,
                          "task_id": k[-1], "role": c.get("role"),
                          "attempt": att, "timeout_s": c.get("timeout_s"),
                          "latency_ms": c.get("latency_ms"),
                          # 失敗通有沒有留下「為什麼」。兩個子句都是活的：
                          #   error        ── brain_cline 失敗通寫的例外字串（在白名單上）
                          #   has_response ── _project_call 投影出的 bool（response 本身不進來）
                          "reason_recorded": bool(c.get("error") or c.get("has_response")),
                          "reason": (str(c.get("error"))[:200] if c.get("error")
                                     else ("<response present, no error>"
                                           if c.get("has_response") else None))})

    common = sorted(k for k in used if k in logged)
    sum_used = sum(used[k] or 0 for k in common)
    sum_logged = sum(logged[k] for k in common)
    sum_retry = sum(retries[k] for k in common)
    residual = sum_logged - sum_used
    per_pair_bad = [{"key": list(k), "logged": logged[k],
                     "calls_used": used[k], "retries": retries[k]}
                    for k in common if logged[k] - (used[k] or 0) != retries[k]]

    holds = (residual == sum_retry) and not per_pair_bad
    if MUTANT == "identity_always_true":   # M1：擋門整段拿掉
        holds = True

    if untagged or len(common) < MIN_PAIRS:
        verdict = "BROKEN"
    elif holds:
        verdict = "ACCOUNTING_CONSISTENT"
    else:
        verdict = "ACCOUNTING_MISMATCH"

    timeouts = [f for f in fails
                if f["timeout_s"] and f["latency_ms"]
                and f["latency_ms"] >= f["timeout_s"] * 1000 * 0.98]
    by_arm = collections.Counter(f["arm"] for f in fails)
    return {
        "verdict": verdict,
        "pairs_with_row": len(used),
        "pairs_matched": len(common),
        "min_pairs_required": MIN_PAIRS,
        "untagged_calls": untagged,
        "untagged_calls_incl_nonexperimental": untagged_all,
        "nonexperimental_calls_by_role": dict(nonexp),
        "sum_calls_used": sum_used,
        "sum_logged_attempts": sum_logged,
        "sum_retry_attempts": sum_retry,
        "residual_logged_minus_used": residual,
        "identity_holds": holds,
        "per_pair_mismatches": per_pair_bad[:10],
        "n_per_pair_mismatches": len(per_pair_bad),
        "request_overhead_pct": (round(100 * residual / sum_used, 3)
                                 if sum_used else None),
        "failed_calls": len(fails),
        "failed_calls_by_arm": dict(by_arm),
        "true_timeout_hits": len(timeouts),
        "failures_with_reason_recorded": sum(1 for f in fails if f["reason_recorded"]),
        "failure_detail": fails[:10],
    }


# ── selftest ────────────────────────────────────────────────────────────────
# 夾具原則（r695/r699）：rows 與 calls 由**兩個互不共用**的建構器造，
# 誰都不從對方導出——否則「檢查 A 與 B 一致」這條擋門結構上沒有夾具看得見它。
LAST_FAILS: list[str] = []


def _build_rows(n, per_task_calls):
    """只造 rows。不知道 calls 長什麼樣。"""
    return [{"arm": "OFF5", "task_id": f"t{i}", "calls_used": per_task_calls,
             # 故意混進結果欄位：白名單若失效，這些會被讀到
             "meets_demand": True, "accepted": True}
            for i in range(n)]


def _build_calls(n, per_task_calls, retry_on=(), untag=(), fail_style="bare"):
    """只造 calls。不讀 rows，重試數由參數獨立指定。

    `fail_style` 決定那通失敗留下什麼：
      "bare"     什麼都沒留（round704 以為 r447 是這樣）
      "error"    留 error 字串（r447 的真實情況）
      "response" 沒有 error 但有 response（只有第二個子句救得了它）

    **回傳的是投影後的 calls**——夾具與真資料走同一條 `_project_call`。
    """
    out = []
    for i in range(n):
        for j in range(per_task_calls):
            meta = {"arm": "OFF5", "task_id": f"t{i}"}
            if i in untag:
                meta = {"task_id": f"t{i}"}          # arm 掉了 ⇒ schema 漂掉
            out.append({"ts_ms": 1000 + i, "role": "gen", "attempt": 1,
                        "ok": True, "timeout_s": 600, "latency_ms": 20000,
                        "meta": meta})
            if i in retry_on and j == 0:
                failed = dict(out[-1], ok=False, latency_ms=600000)
                if fail_style == "error":
                    failed["error"] = f"TimeoutError: timed out (t{i})"
                elif fail_style == "response":
                    failed["response"] = "half-written answer"
                out[-1] = failed
                out.append({"ts_ms": 1001 + i, "role": "gen", "attempt": 2,
                            "ok": True, "timeout_s": 600, "latency_ms": 30000,
                            "meta": meta})
    return [_project_call(c) for c in out]


def selftest() -> int:
    global MUTANT
    LAST_FAILS.clear()
    ok = True

    def ck(label, cond, extra=""):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + label + (f"  {extra}" if extra and not cond else ""))
        if not cond:
            ok = False
            LAST_FAILS.append(label)

    # F1 乾淨：無重試 ⇒ 恆等式成立
    a = audit(_build_rows(30, 5), _build_calls(30, 5))
    ck("F1 乾淨無重試 → ACCOUNTING_CONSISTENT", a["verdict"] == "ACCOUNTING_CONSISTENT", a["verdict"])
    ck("F1b 乾淨時 residual==0", a["residual_logged_minus_used"] == 0)

    # F2 有重試：calls 端多出 2 通，rows 端一個字沒動（只翻一邊）
    a2 = audit(_build_rows(30, 5), _build_calls(30, 5, retry_on=(3, 7)))
    ck("F2 有重試仍 CONSISTENT（重試不計入 calls_used）",
       a2["verdict"] == "ACCOUNTING_CONSISTENT", a2["verdict"])
    ck("F2b 重試數被數出來", a2["sum_retry_attempts"] == 2, str(a2["sum_retry_attempts"]))
    ck("F2c 殘差恰等於重試數", a2["residual_logged_minus_used"] == 2)
    ck("F2d 真逾時被認出（600s 那通）", a2["true_timeout_hits"] == 2, str(a2["true_timeout_hits"]))

    # F3 真的對不上：calls 端多一通 attempt=1（不是重試）⇒ 必須 MISMATCH
    bad = _build_calls(30, 5)
    bad.append(_project_call({"ts_ms": 9999, "role": "gen", "attempt": 1, "ok": True,
                              "timeout_s": 600, "latency_ms": 1000,
                              "meta": {"arm": "OFF5", "task_id": "t3"}}))
    a3 = audit(_build_rows(30, 5), bad)
    ck("F3 多一通未計帳 → ACCOUNTING_MISMATCH", a3["verdict"] == "ACCOUNTING_MISMATCH", a3["verdict"])
    ck("F3b 指得出是哪一格", a3["n_per_pair_mismatches"] == 1, str(a3["n_per_pair_mismatches"]))

    # F4 安靜量不到（型一）：schema 漂掉 ⇒ BROKEN，不准 CONSISTENT
    a4 = audit(_build_rows(30, 5), _build_calls(30, 5, untag=(2,)))
    ck("F4 meta 缺 arm → BROKEN（不是安靜漏掉）", a4["verdict"] == "BROKEN", a4["verdict"])
    ck("F4b 漏掉幾通要報出來", a4["untagged_calls"] == 5, str(a4["untagged_calls"]))

    # F5 安靜量不到（型二）：配對數塌下來 ⇒ BROKEN
    a5 = audit(_build_rows(3, 5), _build_calls(3, 5))
    ck("F5 配對格數 < MIN_PAIRS → BROKEN", a5["verdict"] == "BROKEN", a5["verdict"])

    # F6 rows 領先／落後 calls 是正常的（run 活著）：只取交集，不該紅
    a6 = audit(_build_rows(30, 5), _build_calls(40, 5))
    ck("F6 calls 領先 rows 仍 CONSISTENT（只取交集）",
       a6["verdict"] == "ACCOUNTING_CONSISTENT", a6["verdict"])
    ck("F6b 交集數 = rows 數", a6["pairs_matched"] == 30)

    # F7 失敗通有沒有留下原因。**雙向**：沒留 ⇒ 0；留了 k 通 ⇒ 恰 k。
    # round704 只有前半，而且把「0」寫成預期值 ⇒ 測試在守護錯誤（P-R447-AUDIT-1）。
    ck("F7a 失敗通真的沒留原因 → 0", a2["failures_with_reason_recorded"] == 0,
       str(a2["failures_with_reason_recorded"]))
    a7 = audit(_build_rows(30, 5), _build_calls(30, 5, retry_on=(3, 7), fail_style="error"))
    ck("F7b 失敗通留了 error → 恰 2（不是 0）",
       a7["failures_with_reason_recorded"] == 2, str(a7["failures_with_reason_recorded"]))
    ck("F7b2 分母沒跟著變（仍是 2 通失敗）", a7["failed_calls"] == 2, str(a7["failed_calls"]))
    ck("F7c reason 直接印得出原因字串（收官不必手翻 calls.jsonl）",
       str(a7["failure_detail"][0]["reason"]).startswith("TimeoutError: timed out"),
       str(a7["failure_detail"][0]["reason"]))
    # F7d 第二個子句（has_response）是活的：沒有 error、只有 response 的失敗通也算留了原因。
    # 沒有這條，`error or has_response` 的後半就是死碼（r675 型）。
    a7r = audit(_build_rows(30, 5), _build_calls(30, 5, retry_on=(3, 7), fail_style="response"))
    ck("F7d 只有 response 沒有 error → 仍算留了原因（第二子句非死碼）",
       a7r["failures_with_reason_recorded"] == 2, str(a7r["failures_with_reason_recorded"]))
    ck("F7e 投影只帶 bool，不帶 response 內容",
       all("response" not in c for c in _build_calls(2, 1, retry_on=(0,), fail_style="response")))

    # F9 preflight 豁免：沒標籤但 role 在名單上 ⇒ 不算漏，但舊量必須照樣印出來
    pf = _build_calls(30, 5) + [_project_call(
        {"ts_ms": 1, "role": "preflight", "attempt": 1,
         "ok": True, "meta": {"model": "m"}})]
    a9 = audit(_build_rows(30, 5), pf)
    ck("F9 preflight 不算 schema 漂掉 → CONSISTENT", a9["verdict"] == "ACCOUNTING_CONSISTENT", a9["verdict"])
    ck("F9b 舊語意的量無條件保留", a9["untagged_calls_incl_nonexperimental"] == 1)
    ck("F9c 豁免掉的要具名列出（不准安靜丟）",
       a9["nonexperimental_calls_by_role"] == {"preflight": 1})

    # F9d 這條才是重點：名單**外**的 role 沒標籤，一律照舊 BROKEN。
    # 沒有它，F9 的豁免就等於「任何沒標籤的都放行」。
    unk = _build_calls(30, 5) + [_project_call(
        {"ts_ms": 1, "role": "gen", "attempt": 1,
         "ok": True, "meta": {"model": "m"}})]
    ck("F9d 名單外的 role 沒標籤仍 BROKEN",
       audit(_build_rows(30, 5), unk)["verdict"] == "BROKEN")

    # F8 結果欄位對輸出零影響：把 rows 的結果欄位整批拿掉，audit() 必須逐鍵相同。
    # （_build_rows 刻意混進 meets_demand／accepted；若本體偷讀了它們，這條會紅。）
    stripped = [{k: v for k, v in r.items() if k in ROW_FIELDS}
                for r in _build_rows(30, 5)]
    ck("F8 拿掉結果欄位後輸出逐鍵相同（本體碰不到結果）",
       audit(stripped, _build_calls(30, 5, retry_on=(3,))) ==
       audit(_build_rows(30, 5), _build_calls(30, 5, retry_on=(3,))))

    # ── 植入缺陷：判準是「該吐哪個 verdict 字串」，不是 rc≠0 ────────────────
    muts = [
        ("identity_always_true",   lambda: audit(_build_rows(30, 5), bad),
         "ACCOUNTING_MISMATCH", "M1 擋門整段拿掉"),
        ("retry_off_by_one",       lambda: audit(_build_rows(30, 5), _build_calls(30, 5)),
         "ACCOUNTING_CONSISTENT", "M2 每通都算成重試"),
        ("silently_drop_untagged", lambda: audit(_build_rows(30, 5), _build_calls(30, 5, untag=(2,))),
         "BROKEN", "M3 安靜漏掉沒標籤的通"),
        ("key_ignores_arm",        lambda: audit(_build_rows(30, 5), _build_calls(30, 5)),
         "ACCOUNTING_CONSISTENT", "M4 配對鍵少了 arm"),
        ("no_role_exemption",      lambda: audit(_build_rows(30, 5), pf),
         "ACCOUNTING_CONSISTENT", "M5 拿掉 preflight 豁免"),
    ]
    for name, fn, want_clean, label in muts:
        MUTANT = ""
        base = fn()["verdict"]
        MUTANT = name
        got = fn()["verdict"]
        MUTANT = ""
        ck(f"{label} 乾淨版應為 {want_clean}", base == want_clean, base)
        ck(f"{label} 突變後必須改判（有牙齒）", got != base, f"仍是 {got}")

    # ── M6/M7：投影層的突變體。判準是 **F7 那個數字**，不是 verdict ────────
    # verdict 在這兩個突變下**不會變**（帳目恆等式跟失敗原因無關），所以
    # 若沿用上面那個「verdict 必須改判」的判法，這兩條就是沒牙齒的假測試。
    # M6 重演的正是 r447 真的發生過的缺陷：白名單把 error 剝掉。
    for name, style, label in (
            ("whitelist_strips_error", "error", "M6 白名單剝掉 error"),
            ("whitelist_strips_response_flag", "response", "M7 白名單剝掉 response 旗標")):
        MUTANT = ""
        clean = audit(_build_rows(30, 5), _build_calls(30, 5, retry_on=(3, 7), fail_style=style))
        MUTANT = name
        mut = audit(_build_rows(30, 5), _build_calls(30, 5, retry_on=(3, 7), fail_style=style))
        MUTANT = ""
        ck(f"{label} 乾淨版數到 2", clean["failures_with_reason_recorded"] == 2,
           str(clean["failures_with_reason_recorded"]))
        ck(f"{label} 突變後掉到 0（有牙齒）", mut["failures_with_reason_recorded"] == 0,
           str(mut["failures_with_reason_recorded"]))
        ck(f"{label} 突變後 verdict 不變 ⇒ 證明用 verdict 判會漏掉它",
           mut["verdict"] == clean["verdict"], f"{mut['verdict']} vs {clean['verdict']}")

    print(("SELFTEST OK" if ok else "SELFTEST FAILED ") + ("" if ok else str(LAST_FAILS)))
    return 0 if ok else 1


def main() -> int:
    global MUTANT
    MUTANT = os.environ.get("MUTANT", "")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.run:
        ap.error("--run 或 --selftest 二選一")
    d = pathlib.Path(args.run)
    raw = (d / "rows.jsonl").read_bytes()
    rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    calls = [json.loads(l) for l in (d / "calls.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    # 只留白名單欄位再送進 audit()：白名單是結構性的，不靠 audit() 自律。
    # 與 selftest 夾具共用 `_project_call`（r699：夾具不走同一條就驗不到投影本身）
    calls = [_project_call(c) for c in calls]
    rows = [{k: v for k, v in r.items() if k in ROW_FIELDS} for r in rows]
    out = audit(rows, calls)
    out["rows_lines"] = len(rows)
    out["rows_sha256_16"] = hashlib.sha256(raw).hexdigest()[:16]
    out["run"] = str(d)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0 if out["verdict"] != "BROKEN" else 1


if __name__ == "__main__":
    sys.exit(main())
