#!/usr/bin/env python3
"""R476：R461 收官仲裁者的漂移回歸——附錄 C/D/E 說「已原樣跑過」，之後工具被改了。

判準先行：`DECISION_20260904_R476_R461_CLOSING_ARBITER_DRIFT.md`（`700f114`，本檔之前 commit）。
四格分類、八條事前預測、雙向校準、推翻條件都在那裡，本檔只是編碼它。

四格（判準 §二，不准事後加格／合併）：
    REPRODUCED       附錄逐字記下的每一個量今天都相同（逐鍵比對，不比整檔 sha）
    DRIFTED_SAFE     有差異，且只朝「今天更嚴格／更會叫」的方向
    DRIFTED_UNSAFE   有差異，且會讓收官讀到不同的頭條數字，或今天更寬鬆
    BROKEN           跑不起來／crash／輸出不是合法 JSON ⇒ 不進任何一格（crash 不算偵測到）

擋門：
    G-LIVE  任何含 `g_r461_lcb3_three_arm` 的路徑字串 ⇒ RuntimeError（主 run 零讀取）
    B-LIT   每個釘死的期望字面必須在 R461 預註冊原文裡逐字找得到，否則 EXPECT_NOT_IN_PREREG
            （防止我在本檔自己發明期望值＝量完再訂判準）
    B-NEG   負對照（附錄 D，工具未改）若不是 REPRODUCED ⇒ 全部作廢（判準 §四.1）
    B-CAL   正對照（故意改一個字元的期望值）若不是 DRIFTED ⇒ 全部作廢（判準 §五）

用法：
  python3 ops/gain/r476_closing_arbiter_drift.py --selftest
  python3 ops/gain/r476_closing_arbiter_drift.py --json ops/gain/data/r476_drift.json
"""
from __future__ import annotations
import argparse, json, pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PREREG = ROOT / "DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md"
TWIN = "runs/g_r447_conform_lcb2"          # 已收官的結構孿生
LIVE = "g_r461_lcb3_three_arm"             # 主 run：本輪一個 byte 都不准讀
MUTANT = ""
SUBPROC_TIMEOUT_S = 900        # R476b：r447_eq5_offline --bank lcb2 實測 445.9s，原本寫死的 300s 是夾具缺陷

# ── 釘死的期望值：全部逐字抄自 R461 預註冊的附錄，B-LIT 會回頭驗它們在原文裡 ──
# direction: EXACT            任何差異 ⇒ DRIFTED_UNSAFE
#            MORE_CHECKS_SAFE 條數變多且仍 PASS ⇒ DRIFTED_SAFE
#            MORE_STRICT_SAFE 今天不再放行（verdict 不是 OK）⇒ DRIFTED_SAFE
ITEMS = {
    # 附錄 D.4（負對照：r447_eq5_offline.py 在附錄之前就定版，之後未改）
    "D4_lcb2_regression": dict(direction="EXACT", lits=["cfed36ff71b871f0"]),
    "D4_lcb3_trap":       dict(direction="EXACT", lits=["task_not_in_bank"]),
    # 附錄 C.4（paired_ci.py 於 6ad574e 22:38 被 R471 改過）
    "C4_conform_vs_off":  dict(direction="EXACT", lits=["+19.17pp", "+8.80", "+26.46"]),
    "C4_off5_vs_off":     dict(direction="EXACT", lits=["+12.50pp", "+3.12", "+19.19"]),
    # 附錄 E.4 Y1／Y2、E.3 表（r447_gauge_capability.py 於 22:53-22:56 被 R472 改過三次）
    "E4_Y1_selftest":     dict(direction="MORE_CHECKS_SAFE", lits=["14 條 ck 全綠"]),
    "E4_Y2_real":         dict(direction="EXACT", lits=["21.667", "rows_file_lines=360"]),
    "E3_trunc_23":        dict(direction="MORE_STRICT_SAFE", lits=["28.571"]),
    "E3_trunc_180":       dict(direction="MORE_STRICT_SAFE", lits=["25.0"]),
    # 附錄 B（C.1 已判死；記錄「它仍然是壞的」）
    "B_pooled_single_stratum": dict(direction="EXACT", lits=["rc=2"]),
}

EXPECT = {
    "D4_lcb2_regression": {"rc": 0, "verdict": "RECONSTRUCTED", "calib": 54, "calib_n": 54,
                           "gate": 81, "vote": 76, "b": 14, "c": 9,
                           "delta_pp": 4.1667, "rows": 360, "sha": "cfed36ff71b871f0"},
    "D4_lcb3_trap": {"rc": 0, "verdict": "BROKEN", "paired_null": True,
                     "n_task_not_in_bank": 120, "sampling_bank": "lcb3"},
    "C4_conform_vs_off": {"rc": 0, "n": 120, "b": 31, "c": 8, "delta_pp": 19.17,
                          "lo_pp": 8.80, "hi_pp": 26.46, "p": 0.0003,
                          "verdict": "ON_WINS", "key": "deliv"},
    "C4_off5_vs_off": {"rc": 0, "n": 120, "b": 22, "c": 7, "delta_pp": 12.50,
                       "lo_pp": 3.12, "hi_pp": 19.19, "p": 0.0081,
                       "verdict": "ON_WINS", "key": "deliv"},
    "E4_Y1_selftest": {"rc": 0, "pass": True, "n_checks": 14},
    "E4_Y2_real": {"rc": 0, "verdict": "OK", "n_tasks_complete": 120,
                   "n_tasks_partial_excluded": 0, "n_demonstrated": 94,
                   "n_undemonstrated": 26, "pct_undemonstrated": 21.667,
                   "window_doubt_triggered": False, "deliv_contract_drift": None,
                   "rows_file_lines": 360},
    "E3_trunc_23":  {"verdict": "OK", "n_tasks_complete": 7, "pct_undemonstrated": 28.571},
    "E3_trunc_180": {"verdict": "OK", "n_tasks_complete": 60, "pct_undemonstrated": 25.0},
    "B_pooled_single_stratum": {"rc": 2},
}


# ────────────────────────── 擋門 ──────────────────────────
def guard_live(parts) -> None:
    """G-LIVE：主 run 的任何路徑一律拒絕。"""
    if MUTANT == "M5_live_gate_off":
        return
    for p in parts:
        if LIVE in str(p):
            raise RuntimeError(f"G-LIVE：本輪不准碰主 run（{p}）")


def lits_in_prereg(text: str, items=None) -> dict:
    """B-LIT：釘死的期望字面是不是真的在預註冊原文裡。"""
    out = {}
    for k, meta in (items or ITEMS).items():
        if MUTANT == "M1_lit_gate_toothless":
            out[k] = True
            continue
        out[k] = all(bool(l) and (l in text) for l in meta["lits"])
    return out


# ────────────────────────── 比對器 ──────────────────────────
def _eq(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 5e-3
        except (TypeError, ValueError):
            return False
    return a == b


def classify(item: str, expected: dict, observed: dict | None, direction: str) -> dict:
    """判準 §二 的四格。observed=None ⇒ BROKEN。"""
    if observed is None or observed.get("_broken"):
        return {"item": item, "box": "BROKEN",
                "why": (observed or {}).get("_broken", "沒有產出")}
    # ── R476b 新增：BROKEN_PROJECTION ──
    # 期望值不是 None、卻投影成 None ⇒ 夾具「沒讀到」，跟「工具漂移」在輸出上長得一模一樣
    # （memory r705：白名單剝掉鍵 ⇒ 把「讀不到」報成「沒落盤」）。這一格是 BROKEN 不是 DRIFTED。
    # **邊界（自己寫死）**：只對 EXACT／MORE_CHECKS_SAFE 生效——那兩種的輸入是完好的，
    # 讀不到就是夾具壞了。MORE_STRICT_SAFE 的輸入是**故意截斷**的，工具在 BROKEN 時
    # 拒吐能力數字正是 R472 擋門在做它該做的事，那個 None 是訊號不是缺陷。
    if direction in ("EXACT", "MORE_CHECKS_SAFE") and MUTANT != "M6_projection_gate_off":
        missing = sorted(k for k, v in expected.items()
                         if v is not None and observed.get(k) is None)
        if missing:
            return {"item": item, "box": "BROKEN",
                    "why": f"BROKEN_PROJECTION：夾具沒有讀到 {missing}（不是工具漂移）",
                    "missing": missing}
    diffs = {k: {"expected": v, "observed": observed.get(k)}
             for k, v in expected.items() if not _eq(v, observed.get(k))}
    if MUTANT == "M2_ignore_diffs":
        diffs = {}
    if not diffs:
        return {"item": item, "box": "REPRODUCED", "diffs": {}}
    if MUTANT == "M3_all_drift_is_safe":
        return {"item": item, "box": "DRIFTED_SAFE", "diffs": diffs}
    if direction == "MORE_CHECKS_SAFE":
        safe = (set(diffs) <= {"n_checks"}
                and (observed.get("n_checks") or 0) > expected["n_checks"]
                and observed.get("pass") is True)
    elif direction == "MORE_STRICT_SAFE":
        safe = observed.get("verdict") != "OK"
    else:                                       # EXACT
        safe = False
    return {"item": item, "box": "DRIFTED_SAFE" if safe else "DRIFTED_UNSAFE",
            "diffs": diffs}


# ────────────────────────── 跑指令 ──────────────────────────
def run(argv: list[str], cwd=None, timeout=SUBPROC_TIMEOUT_S) -> dict:
    guard_live(argv)
    try:
        p = subprocess.run([sys.executable] + argv, cwd=str(cwd or ROOT),
                           capture_output=True, text=True, timeout=timeout)
    except Exception as e:                                   # noqa: BLE001
        return {"_broken": f"subprocess 失敗：{e}"}
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}


def _json_tail(s: str):
    """從 stdout 取最後一個頂層 JSON 物件；取不到回 None。"""
    i = s.find("{")
    while i != -1:
        try:
            return json.loads(s[i:])
        except json.JSONDecodeError:
            i = s.find("{", i + 1)
    return None


# ── 每個 item 的觀測器：把工具輸出投影成 EXPECT 的鍵 ──
def obs_D4(bank: str) -> dict:
    r = run(["ops/gain/r447_eq5_offline.py", "--run", TWIN, "--bank", bank])
    if r.get("_broken"):
        return r
    j = _json_tail(r["out"])
    if j is None:
        return {"_broken": "r447_eq5_offline 沒有吐出合法 JSON"}
    o = {"rc": r["rc"], "verdict": j.get("verdict")}
    if bank == "lcb2":
        rr = j.get("rule_rates") or {}
        cal = j.get("calibration") or {}
        pg = j.get("paired_gate_vs_vote") or {}
        # R476b：鍵名逐個對照工具真的吐出來的 schema（原本的 n_ok／b／c／receipt.* 都不存在
        # ⇒ 投影成 None ⇒ 會被記成 DRIFTED_UNSAFE，而真相是「夾具沒讀到」）
        o.update(calib=cal.get("agree"), calib_n=cal.get("n"),
                 gate=rr.get("gate_deliv_correct"), vote=rr.get("vote_deliv_correct"),
                 b=pg.get("b_gate_only"), c=pg.get("c_vote_only"),
                 delta_pp=pg.get("delta_pp"),
                 rows=j.get("rows_lines"),
                 sha=j.get("rows_sha256_16"))
    else:
        o.update(paired_null=(j.get("paired_gate_vs_vote") is None),
                 n_task_not_in_bank=sum(1 for x in (j.get("broken") or [])
                                        if "task_not_in_bank" in str(x)),
                 sampling_bank=(j.get("sampling") or {}).get("bank"))
    o["_raw"] = j
    return o


def obs_C4(a_arm: str) -> dict:
    # R476b：paired_ci 的 stdout 是給人看的文字，機器讀的 JSON 只走 --json 檔。
    # （memory：--json 的檔不可以跟 stdout 導向的檔同一個；這裡 stdout 沒有被導向檔案。）
    jf = pathlib.Path(f"/dev/shm/r476_pairedci_{a_arm}.json")
    if jf.exists():
        jf.unlink()
    r = run(["ops/gain/replay/paired_ci.py", "--run", TWIN,
             "--a-arm", a_arm, "--b-arm", "OFF", "--key", "deliv", "--json", str(jf)])
    if r.get("_broken"):
        return r
    j = json.loads(jf.read_text(encoding="utf-8")) if jf.exists() else None
    if j is None:
        return {"_broken": "paired_ci 沒有寫出 --json 檔"}
    return {"rc": r["rc"], "n": j.get("n_paired"), "b": j.get("b_discordant_a_only"),
            "c": j.get("c_discordant_b_only"), "delta_pp": j.get("delta_pp"),
            "lo_pp": j.get("ci95_lo_pp"), "hi_pp": j.get("ci95_hi_pp"),
            "p": j.get("p_mcnemar_exact"), "verdict": j.get("verdict"),
            "key": j.get("key"), "_raw": j}


def obs_E4_Y1() -> dict:
    r = run(["ops/gain/r447_gauge_capability.py", "--selftest"])
    if r.get("_broken"):
        return r
    txt = r["out"] + r["err"]
    # 條數＝selftest 逐條印出來的行數（工具用 "  <名字> ..." 的格式）
    n = len([ln for ln in txt.splitlines()
             if re.match(r"^\s*(ck_)?[A-Z]\w*\s", ln) and "SELFTEST" not in ln])
    return {"rc": r["rc"], "pass": "SELFTEST_PASS" in txt, "n_checks": n, "_text": txt}


def obs_gauge(run_dir: str) -> dict:
    r = run(["ops/gain/r447_gauge_capability.py", run_dir])
    if r.get("_broken"):
        return r
    j = _json_tail(r["out"])
    if j is None:
        return {"_broken": "r447_gauge_capability 沒有吐出合法 JSON"}
    o = {k: j.get(k) for k in ("verdict", "n_tasks_complete", "n_tasks_partial_excluded",
                               "n_demonstrated", "n_undemonstrated", "pct_undemonstrated",
                               "window_doubt_triggered", "deliv_contract_drift",
                               "rows_file_lines")}
    o["rc"] = r["rc"]
    o["_raw"] = j
    return o


def obs_trunc(nlines: int) -> dict:
    """E.3 的截斷實驗：在 /dev/shm 的複本上做，runs/ 底下一個檔都不動。"""
    dst = pathlib.Path(f"/dev/shm/r476_trunc_{nlines}")
    guard_live([dst])
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    src = ROOT / TWIN
    for name in ("summary.json", "notes.jsonl"):
        if (src / name).exists():
            shutil.copy2(src / name, dst / name)
    lines = (src / "rows.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)
    (dst / "rows.jsonl").write_text("".join(lines[:nlines]), encoding="utf-8")
    return obs_gauge(str(dst))


def obs_B_pooled() -> dict:
    r = run(["ops/gain/replay/pooled_paired_ci.py",
             "--stratum", f"lcb3={TWIN}", "--a-arm", "CONFORM",
             "--b-arm", "OFF", "--key", "deliv"])
    if r.get("_broken"):
        return r
    return {"rc": r["rc"], "_text": (r["out"] + r["err"])[-400:]}


# ────────────────────────── 自檢 ──────────────────────────
def selftest() -> int:
    fails = []

    def ck(name, got, want):
        ok = got == want
        print(f"  {name:34s} {str(got):22s} (期望 {want})")
        if not ok:
            fails.append(name)

    e = {"rc": 0, "verdict": "OK", "x": 1.5}
    ck("A_identical_is_reproduced",
       classify("t", e, dict(e), "EXACT")["box"], "REPRODUCED")
    ck("B_exact_diff_is_unsafe",
       classify("t", e, {**e, "x": 2.5}, "EXACT")["box"], "DRIFTED_UNSAFE")
    ck("C_more_checks_is_safe",
       classify("t", {"n_checks": 14, "pass": True},
                {"n_checks": 16, "pass": True}, "MORE_CHECKS_SAFE")["box"], "DRIFTED_SAFE")
    ck("D_fewer_checks_is_unsafe",
       classify("t", {"n_checks": 14, "pass": True},
                {"n_checks": 12, "pass": True}, "MORE_CHECKS_SAFE")["box"], "DRIFTED_UNSAFE")
    ck("E_stricter_is_safe",
       classify("t", {"verdict": "OK", "n": 7}, {"verdict": "BROKEN_X", "n": 7},
                "MORE_STRICT_SAFE")["box"], "DRIFTED_SAFE")
    ck("F_still_ok_is_unsafe",
       classify("t", {"verdict": "OK", "n": 7}, {"verdict": "OK", "n": 9},
                "MORE_STRICT_SAFE")["box"], "DRIFTED_UNSAFE")
    ck("G_broken_is_its_own_box",
       classify("t", e, {"_broken": "boom"}, "EXACT")["box"], "BROKEN")
    ck("H_float_tolerance", classify("t", {"x": 21.667}, {"x": 21.667}, "EXACT")["box"],
       "REPRODUCED")
    # G-LIVE 有牙齒
    hit = False
    try:
        guard_live([f"runs/{LIVE}/rows.jsonl"])
    except RuntimeError:
        hit = True
    ck("I_live_gate_bites", hit, True)
    ck("J_live_gate_lets_twin_through", (guard_live([TWIN]) is None), True)
    # B-LIT 有牙齒：發明一個原文裡沒有的字面
    ck("K_lit_gate_bites",
       lits_in_prereg(PREREG.read_text(encoding="utf-8"),
                      {"fake": {"lits": ["這句話不在預註冊裡_zzz"]}})["fake"], False)
    # 正對照（判準 §五）：把期望值改一個字元 ⇒ 必須 DRIFTED，不准 REPRODUCED
    # R476b：投影擋門的三條（正／負／邊界）
    ck("M_projection_none_is_broken",
       classify("t", {"rows": 360}, {"rows": None}, "EXACT")["box"], "BROKEN")
    ck("N_expected_none_is_not_broken",
       classify("t", {"deliv_contract_drift": None}, {"deliv_contract_drift": None},
                "EXACT")["box"], "REPRODUCED")
    ck("O_strict_withheld_is_still_safe",
       classify("t", {"verdict": "OK", "pct": 28.571},
                {"verdict": "BROKEN_ROW_ACCOUNTING", "pct": None},
                "MORE_STRICT_SAFE")["box"], "DRIFTED_SAFE")
    ck("L_positive_control_flip",
       classify("t", {"sha": "cfed36ff71b871f0"}, {"sha": "cfed36ff71b871f1"},
                "EXACT")["box"], "DRIFTED_UNSAFE")
    print("SELFTEST_" + ("FAIL " + ",".join(fails) if fails else "PASS"))
    return 1 if fails else 0


# ────────────────────────── 主流程 ──────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    text = PREREG.read_text(encoding="utf-8")
    lit = lits_in_prereg(text)
    observers = {
        "D4_lcb2_regression": lambda: obs_D4("lcb2"),
        "D4_lcb3_trap":       lambda: obs_D4("lcb3"),
        "C4_conform_vs_off":  lambda: obs_C4("CONFORM"),
        "C4_off5_vs_off":     lambda: obs_C4("OFF5"),
        "E4_Y1_selftest":     obs_E4_Y1,
        "E4_Y2_real":         lambda: obs_gauge(TWIN),
        "E3_trunc_23":        lambda: obs_trunc(23),
        "E3_trunc_180":       lambda: obs_trunc(180),
        "B_pooled_single_stratum": obs_B_pooled,
    }
    results, raw = {}, {}
    for k, meta in ITEMS.items():
        o = observers[k]()
        raw[k] = {kk: vv for kk, vv in o.items() if not kk.startswith("_")} if o else None
        results[k] = classify(k, EXPECT[k], o, meta["direction"])
        results[k]["lit_in_prereg"] = lit.get(k)

    boxes = {}
    for r in results.values():
        boxes[r["box"]] = boxes.get(r["box"], 0) + 1

    # 擋門
    gates = {}
    gates["B_LIT"] = "OK" if all(lit.values()) else \
        "EXPECT_NOT_IN_PREREG:" + ",".join(k for k, v in lit.items() if not v)
    neg = [results[k]["box"] for k in ("D4_lcb2_regression", "D4_lcb3_trap")]
    gates["B_NEG"] = "OK" if set(neg) == {"REPRODUCED"} else f"NEGATIVE_CONTROL_FAILED:{neg}"
    # B-CAL：在**真觀測**上把期望值改一個字元 ⇒ 必須 DRIFTED（不是憑合成夾具）
    cal_src = raw.get("E4_Y2_real") or {}
    cal_box = classify("cal", {**EXPECT["E4_Y2_real"], "pct_undemonstrated": 99.999},
                       cal_src or None, "EXACT")["box"]
    gates["B_CAL"] = "OK" if cal_box.startswith("DRIFTED") else f"CALIBRATION_FAILED:{cal_box}"

    verdict = "OK" if all(v == "OK" for v in gates.values()) else "BROKEN"
    if verdict == "OK" and boxes.get("DRIFTED_UNSAFE"):
        verdict = "DRIFT_UNSAFE_PRESENT"
    out = {"verdict": verdict, "gates": gates, "boxes": boxes,
           "results": results, "observed": raw,
           "live_run_reads": 0, "twin": TWIN}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if a.json:
        pathlib.Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if verdict != "BROKEN" else 2


if __name__ == "__main__":
    MUTANT = __import__("os").environ.get("R476_MUTANT", "")
    sys.exit(main())
