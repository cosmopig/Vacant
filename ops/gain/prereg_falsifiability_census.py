#!/usr/bin/env python3
"""R453：對 R440Z 的每一條預註冊判準問「它有可能是假的嗎？」——零 API、純本機。

判準先行：`DECISION_20260904_R453_PREREG_FALSIFIABILITY_CENSUS.md`（0c31559，本檔之前
commit）。分類規則、事前預測表、P-Z5b 的恆等式、推翻條件都在那裡，本檔只是編碼它。

三格分類（DECISION §二，不准事後加格）：
    EVALUABLE    證偽事件在資料裡出現過（或候選恆等式被反例推翻）⇒ HIT 帶資訊
    FORCED_GREEN 寫得出恆等式 **且** witness＝0 ⇒ HIT 不帶資訊，收官要附恆等式與基準率
    UNRESOLVED   兩者皆無 ⇒ 照實寫「判不出來」，不准往任何一邊倒

⚠ `EVALUABLE` 只表示「可能為假」，**不表示這個 n 分得出來**——後者的仲裁者是 R451 的
MDE／N₈₀（DECISION §二）。兩者不准互相冒充。

擋門（判準不是 rc≠0）：
    B1 恆等式成立 **且** witness>0 ⇒ CONTRADICTION（DECISION §六.1 比本檔的主張優先）
    B2 `n_unparsed_shape > 0` ⇒ FORCED 降級成 `FORCED_ON_PARSED`，認不出的題數具名列出
    B3 被引用的原始碼運算式與釘死的字面不符 ⇒ SOURCE_DRIFT（不是「證明成立」）
    B4 完整（三臂都有列）的題目 < MIN_TASKS ⇒ UNCALIBRATED，不吐分類
    B5 CONTRADICTION／SOURCE_DRIFT 時不准吐任何 FORCED_GREEN

用法：
  python3 ops/gain/prereg_falsifiability_census.py --selftest
  python3 ops/gain/prereg_falsifiability_census.py --run runs/g_r447_conform_lcb2 \
      --json ops/gain/data/r453_census.json
"""
from __future__ import annotations
import argparse, ast, hashlib, json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.gain.gain_run import load_tasks                                # noqa: E402
from ops.gain.analyze_r447 import _deliv                                # noqa: E402
from ops.gain.power_paired import exact_mcnemar_p                       # noqa: E402
from ops.gain.r447_eq5_offline import bank_gate_headroom                # noqa: E402
from ops.gain import r447_reject_reconstruct as RR                      # noqa: E402

MUTANT = ""
LAST_FAILS: list[str] = []

MIN_TASKS = 20                      # B4
PREREG = ROOT / "DECISION_20260904_R440Z_LCB2_PREREG.md"

# R440Z §三 的窗口。**每一條都要在 R440Z 原文裡逐字找得到**（見 _windows_in_prereg），
# 否則就是我在這裡自己發明窗口——那正是「量完再訂判準」。
WINDOWS = {
    "P-Z1":  ("OFF 失敗率", (40.0, 60.0), "40–60%"),
    "P-Z2b": ("CONFORM−OFF 交付差 pp", (12.0, 25.0), "+12 到 +25pp"),
    "P-Z3":  ("CONFORM−OFF5 交付差 pp", (2.0, 8.0), "+2 到 +8pp"),
    "P-Z4":  ("CONFORM calls_per_task", (1.5, 2.2), "1.5–2.2"),
    "P-Z5a": ("CONFORM 拒交率", (5.0, 12.0), "5–12%"),
}

# 被引用的原始碼運算式（B3）。key -> (檔案, 函式, 期望的逐字字串)。
# 記憶鐵律：驗程式碼在什麼條件為真，要用 ast 逐字取出真運算式，不准自己改寫一份。
SOURCE_CLAIMS = {
    # DECISION §四：拒交 ⟺ 全部候選 ¬V（因為 arm_conform 把 visible_ok 寫成 accepted 本身）
    "conform_visible_ok_is_accepted": ("ops/gain/gain_run.py", "arm_conform",
                                       '"visible_ok": accepted'),
}


# ──────────────────────────────────────────────────────────────────────
# 前置尺
# ──────────────────────────────────────────────────────────────────────
def _windows_in_prereg(text: str, windows=None) -> dict:
    """每個窗口的字面是不是真的在 R440Z 原文裡（防止我在本檔發明窗口）。"""
    out = {}
    for pid, (_, _, literal) in (windows or WINDOWS).items():
        if MUTANT == "Y8_window_check_toothless":
            out[pid] = True                      # 不看原文就宣稱在＝沒牙齒
            continue
        out[pid] = bool(literal) and (literal in text)
    return out


def _source_segment(relpath: str, funcname: str) -> str | None:
    """把某個函式的原始碼逐字取出（`ast.get_source_segment`），取不到回 None。"""
    src = (ROOT / relpath).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == funcname:
            return ast.get_source_segment(src, node)
    return None


def check_source_claims(claims=None) -> dict:
    """B3：本檔引用的每一條原始碼事實，逐字比對；對不上就是 SOURCE_DRIFT。"""
    out = {}
    for key, (rel, fn, literal) in (claims or SOURCE_CLAIMS).items():
        seg = _source_segment(rel, fn)
        found = bool(seg) and literal in seg
        if MUTANT == "Y5_paraphrase_instead_of_source":
            # ＝「我照記憶自己改寫一份運算式、宣稱原始碼就是這樣」⇒ 永遠成立、永不報漂移
            found = True
        out[key] = {"file": rel, "func": fn, "literal": literal, "found": found}
    out["drift"] = sorted(k for k, v in out.items() if isinstance(v, dict) and not v["found"])
    return out


def receipt_key_by_arm(src: str | None = None) -> dict:
    """P-Z8 前半：`receipt_head` 在哪些 arm_* 的 return dict 裡是**無條件字面鍵**。

    無條件＝該函式的每一個 `Return` 的 dict 裡都有這個字面 key。有任何一條 return
    沒有它，就不是恆真（那條路徑會產出缺鍵的列）。
    """
    if src is None:
        src = (ROOT / "ops/gain/gain_run.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("arm_")):
            continue
        rets = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
        has = []
        for r in rets:
            keys = set()
            for sub in ast.walk(r):
                if isinstance(sub, ast.Dict):
                    keys |= {k.value for k in sub.keys
                             if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            has.append("receipt_head" in keys)
        if MUTANT == "Y7_receipt_any_return_counts":
            out[node.name] = {"n_returns": len(rets), "unconditional": bool(has) and any(has)}
        else:
            out[node.name] = {"n_returns": len(rets), "unconditional": bool(has) and all(has)}
    return out


# ──────────────────────────────────────────────────────────────────────
# 統計量與留一法
# ──────────────────────────────────────────────────────────────────────
def per_task(rows: list[dict]) -> list[dict]:
    """三臂都有列的題目，逐題一筆。缺任一臂就不算（分母要對得起配對）。"""
    by: dict[str, dict] = {}
    for r in rows:
        by.setdefault(r["task_id"], {})[r.get("arm")] = r
    out = []
    for tid, d in sorted(by.items()):
        if not {"OFF", "CONFORM", "OFF5"} <= set(d):
            continue
        out.append({
            "task_id": tid,
            "off_correct": bool(d["OFF"].get("meets_demand")),
            "off_deliv": _deliv(d["OFF"]),
            "conform_deliv": _deliv(d["CONFORM"]),
            "off5_deliv": _deliv(d["OFF5"]),
            "conform_accepted": bool(d["CONFORM"].get("accepted")),
            "conform_calls": float(d["CONFORM"].get("calls_used") or 0),
        })
    return out


def _stat(pt: list[dict], name: str) -> float | None:
    """五個區間型判準的統計量。分母＝三臂都有列的題目（與 per_task 同一個）。"""
    if not pt:
        return None
    n = len(pt)
    if name == "P-Z1":
        return 100.0 * sum(1 for p in pt if not p["off_correct"]) / n
    if name == "P-Z4":
        return sum(p["conform_calls"] for p in pt) / n
    if name == "P-Z5a":
        return 100.0 * sum(1 for p in pt if not p["conform_accepted"]) / n
    if name == "P-Z2b":
        return 100.0 * (sum(p["conform_deliv"] for p in pt)
                        - sum(p["off_deliv"] for p in pt)) / n
    if name == "P-Z3":
        return 100.0 * (sum(p["conform_deliv"] for p in pt)
                        - sum(p["off5_deliv"] for p in pt)) / n
    raise KeyError(name)


def jackknife_escapes(pt: list[dict], name: str, lo: float, hi: float) -> dict:
    """留一法可及性：逐題留一重算，有任一個落到窗外就是 EVALUABLE（沒有可調參數）。"""
    vals = []
    for i in range(len(pt)):
        sub = pt if MUTANT == "Y4_jackknife_no_leaveout" else pt[:i] + pt[i + 1:]
        v = _stat(sub, name)
        if v is not None:
            vals.append(v)
    esc = [v for v in vals if v < lo or v > hi]
    full = _stat(pt, name)
    # ── 解析度（**非仲裁者**，additive，不改任何分類）
    # 留一法只是 1/n 擾動 ⇒ 只有當點估計落在窗口邊界「一個擾動」以內時才可能逃出去。
    # 沒有這個數字，UNRESOLVED 會被下一輪讀成「這個窗口不可證偽」——而它其實只是
    # 「這把尺沒有解析度」。與 R451 對 UNINFORMATIVE 要求附 MDE／N₈₀ 是同一條紀律。
    pert = max((abs(v - full) for v in vals), default=None) if full is not None else None
    dist = min(full - lo, hi - full) if full is not None else None
    if MUTANT == "Y9_resolution_ignores_perturbation":
        pert = dist                       # 比值恆為 1 ⇒ 永遠看起來「剛好有解析度」
    return {"full": full, "n_replicates": len(vals),
            "min": min(vals) if vals else None, "max": max(vals) if vals else None,
            "n_outside_window": len(esc), "reachable": bool(esc),
            "instrument_resolution_NOT_ARBITER": {
                "max_loo_perturbation": pert,
                "distance_to_nearest_boundary": dist,
                # pert==0（留一法完全不動）⇒ 比值定義成 inf／0，不吐 None：
                # None 會讓下游的比較 crash，而 crash 收場不算偵測到（r699）。
                "boundary_over_perturbation": (
                    (dist / pert) if pert else (math.inf if (dist or 0) > 0 else 0.0)),
                "note": ("比值 ≫1 ⇒ 本輪的 UNRESOLVED 是「留一法沒有解析度」，"
                         "**不是**「這個窗口不可證偽」。距離為負＝點估計已經在窗外"
                         "（證偽事件已實現），那不是解析度問題。不改任何分類。")}}


def paired_bc(pt: list[dict], a: str, b: str) -> tuple[int, int]:
    bb = sum(1 for p in pt if p[a] and not p[b])
    cc = sum(1 for p in pt if p[b] and not p[a])
    return bb, cc


# ──────────────────────────────────────────────────────────────────────
# 分類
# ──────────────────────────────────────────────────────────────────────
def classify(identity: bool, witnesses: int, *, forced_on_parsed: bool = False) -> str:
    """DECISION §二 的三格。順序寫死：witness 優先於恆等式，兩者並存＝CONTRADICTION。"""
    if MUTANT == "Y2_witness_ignored" and identity:
        return "FORCED_GREEN"
    if identity and witnesses > 0:
        return "CONTRADICTION"
    if witnesses > 0:
        return "EVALUABLE"
    if identity:
        return "FORCED_ON_PARSED" if forced_on_parsed else "FORCED_GREEN"
    return "UNRESOLVED"


def census(rows, calls, tasks, runs_dir=None, *, recon=None, windows=None) -> dict:
    out: dict = {"broken": [], "records": {}}
    pt = per_task(rows)
    prereg_text = PREREG.read_text(encoding="utf-8")
    win_ok = _windows_in_prereg(prereg_text, windows)
    src = check_source_claims()
    receipts = receipt_key_by_arm()
    head = bank_gate_headroom(tasks)

    if len(pt) < MIN_TASKS:
        out["verdict"] = "UNCALIBRATED"
        out["n_complete_tasks"] = len(pt)
        return out
    if src["drift"]:
        out["broken"].append(f"source_drift:{src['drift']}")
    for pid, ok in win_ok.items():
        if not ok:
            out["broken"].append(f"window_not_in_prereg:{pid}")

    # ── 恆等式 I1：可見⊆隱藏 ⇒ ¬V → ¬H
    subset_identity = bool(head["forced_zero"])
    on_parsed = head["n_unparsed_shape"] > 0                      # B2
    if MUTANT == "Y1_ignore_unparsed_shape":
        on_parsed = False

    # ── witness（零計數型）
    w_pz6 = [r["task_id"] for r in rows
             if r.get("visible_ok") is False and r.get("meets_demand")]
    cand_bad = recon["candidate_losslessness_EXPLORATORY"]["discarded_but_hidden_ok"]
    rej = recon["pz5b"]["rejected_tasks"]
    rej_wrong = recon["pz5b"]["all_candidates_wrong"]
    w_pz5b = rej - rej_wrong          # 分子少一個 ⟺ 存在 ¬V ∧ H 的候選（DECISION §四）
    if MUTANT == "Y3_pz5b_witness_from_rows_only":
        w_pz5b = 0 if not w_pz6 else len(w_pz6)

    out["records"]["P-Z5b"] = {
        "clause": "拒交題裡「五份全錯」≥ 80%",
        "falsifier": "某個拒交題有候選 hidden 其實是對的（¬V ∧ H）",
        "identity": ("可見⊆隱藏 ⇒ ¬V→¬H；拒交⟺全部¬V ⇒ 全部¬H ⇒ 分子恆＝分母"
                     if subset_identity else None),
        "witnesses": w_pz5b, "observed": recon["pz5b"],
        "subevent_of": "P-Z6/candidate_losslessness（分子要少一個必須先有 ¬V∧H 的候選）",
        "class": classify(subset_identity, w_pz5b, forced_on_parsed=on_parsed)}

    out["records"]["P-Z6"] = {
        "clause": "rows 裡沒有 visible_ok=False ∧ meets_demand=True 的列",
        "falsifier": "出現這種列",
        "identity": "可見⊆隱藏 ⇒ ¬V→¬H" if subset_identity else None,
        "witnesses": len(w_pz6), "witness_task_ids": w_pz6[:10],
        "class": classify(subset_identity, len(w_pz6), forced_on_parsed=on_parsed)}

    out["records"]["candidate_losslessness"] = {
        "clause": "（探索性）閘門沒殺掉好答案",
        "falsifier": "被丟掉的候選裡有 hidden 是對的",
        "identity": "同上" if subset_identity else None,
        "witnesses": cand_bad,
        "observed": recon["candidate_losslessness_EXPLORATORY"],
        "class": classify(subset_identity, cand_bad, forced_on_parsed=on_parsed)}

    # ── 區間型：留一法可及性
    for pid, (label, (lo, hi), literal) in (windows or WINDOWS).items():
        jk = jackknife_escapes(pt, pid, lo, hi)
        out["records"][pid] = {
            "clause": f"{label} 落在 {literal}", "falsifier": "落在窗外",
            "identity": None, "witnesses": jk["n_outside_window"],
            "jackknife": jk, "window_literal_in_R440Z": win_ok[pid],
            "class": classify(False, jk["n_outside_window"])}

    # ── P-Z2a / §六 推翻條件：c 會不會被壓成 0
    b_co, c_co = paired_bc(pt, "conform_deliv", "off_deliv")
    b_c5, c_c5 = paired_bc(pt, "conform_deliv", "off5_deliv")
    out["records"]["P-Z2a"] = {
        "clause": "CONFORM vs OFF p < 0.01", "falsifier": "p ≥ 0.01",
        "identity": None, "witnesses": int(exact_mcnemar_p(b_co, c_co) >= 0.01),
        "observed": {"b": b_co, "c": c_co, "p": exact_mcnemar_p(b_co, c_co)},
        "note": "witness 是「這個 run 現在就落在證偽側」；不是則見 jackknife 之外的 R451 MDE",
        "class": classify(False, int(exact_mcnemar_p(b_co, c_co) >= 0.01))}
    out["records"]["overturn_c_ge_b_half"] = {
        "clause": "（R440Z §六）推翻 P-Z2 的條件：c ≥ b/2 或 p ≥ 0.05",
        "falsifier": "——本項問的是**這個推翻條件本身是否可及**",
        "candidate_forcing_identity": "若 CONFORM 首位候選與 OFF 同源 ⇒ c 恆為 0",
        "witnesses": c_co,          # c>0 ⇒ 上面那條恆等式被反例推翻
        "observed": {"b": b_co, "c": c_co, "c_ge_b_half": c_co >= b_co / 2},
        "class": classify(False, c_co)}
    out["records"]["P-Z3_pvalue"] = {
        "clause": "vs OFF5 p 很可能仍 > 0.05", "falsifier": "p ≤ 0.05",
        "identity": None, "witnesses": int(exact_mcnemar_p(b_c5, c_c5) <= 0.05),
        "observed": {"b": b_c5, "c": c_c5, "p": exact_mcnemar_p(b_c5, c_c5)},
        "class": classify(False, int(exact_mcnemar_p(b_c5, c_c5) <= 0.05))}

    # ── P-Z7：本 run void 恆 0 ⇒ 去別的 run 找 witness（跨 run 才判得出可及性）
    void_w = []
    n_scanned = 0
    if runs_dir is not None:
        for sp in sorted(pathlib.Path(runs_dir).glob("*/summary.json")):
            try:
                sm = json.loads(sp.read_text(encoding="utf-8"))
            except Exception:
                continue
            n_scanned += 1
            for arm, v in (sm.get("arms") or {}).items():
                if isinstance(v, dict) and (v.get("infra_void") or 0) > 0:
                    void_w.append({"run": sp.parent.name, "arm": arm,
                                   "infra_void": v["infra_void"], "tasks": v.get("tasks")})
    # ⚠ 「掃過 N 個 run、都沒有 void」與「一個 run 都沒掃到」是兩件事，長得一模一樣。
    #   後者是安靜量不到 ⇒ 記 UNSCANNED，不准當成 UNRESOLVED 混過去。
    #   （這條是跑在凍結快照上時真的踩到的：快照目錄沒有兄弟 run，witness 從 30 掉到 0。）
    if MUTANT == "Y10_void_scan_silent_when_empty":
        n_scanned = max(n_scanned, 1)
    out["records"]["P-Z7"] = {
        "clause": "任一臂 void < 20%；CONFORM 臂 void < 5%",
        "falsifier": "void 超標", "identity": None,
        "witnesses": len(void_w), "witness_sample": void_w[:5],
        "runs_scanned": n_scanned,
        "note": "本 run void 恆 0 ⇒ 可及性只能跨 run 判；跨 run 的 witness 不是本 run 的證偽",
        "class": ("UNSCANNED" if n_scanned == 0 else classify(False, len(void_w)))}

    # ── P-Z8 前半：receipt_head 是不是無條件字面鍵
    # ⚠ 這一條的恆等式（`arm_conform` 的 return dict）與它的 witness（別臂的列缺鍵）
    #   **不是同一個母體**。合成一筆會讓 §六.1 的 CONTRADICTION 擋門誤觸——
    #   那不是「恆等式被推翻」，是我把兩個範圍疊在一起。自檢 C1/C5 就是這樣抓到的。
    #   故按母體拆成兩筆，並把「P-Z8 的範圍是哪一個」留給收官裁決。
    arms_with = sorted(k for k, v in receipts.items() if v["unconditional"])
    rows_missing_all = sorted({r.get("arm") for r in rows if "receipt_head" not in r})
    conform_missing = [r["task_id"] for r in rows
                       if r.get("arm") == "CONFORM" and "receipt_head" not in r]
    out["records"]["P-Z8_receipt_head@CONFORM"] = {
        "population": "arm=CONFORM 的列",
        "clause": "每列有 receipt_head（範圍讀作 CONFORM 臂）",
        "falsifier": "CONFORM 的列缺這個鍵",
        "identity": ("arm_conform 的每一條 return 的 dict 都有字面鍵 receipt_head"
                     if receipts.get("arm_conform", {}).get("unconditional") else None),
        "witnesses": len(conform_missing),
        "observed": {"unconditional_in": arms_with},
        "class": classify(bool(receipts.get("arm_conform", {}).get("unconditional")),
                          len(conform_missing))}
    out["records"]["P-Z8_receipt_head@ALL_ROWS"] = {
        "population": "rows.jsonl 全部的列",
        "clause": "每列有 receipt_head（範圍照字面讀作全部）",
        "falsifier": "任何臂的列缺這個鍵",
        "identity": None,
        "witnesses": sum(1 for r in rows if "receipt_head" not in r),
        "observed": {"arms_of_rows_missing_key": rows_missing_all},
        "note": "照字面讀，這一條在本 run 已經為假（OFF／OFF5 的列本來就沒這個鍵）。"
                "範圍歧義（全部 vs 只有 CONFORM）不是本尺能裁的，留給收官。",
        "class": classify(False, sum(1 for r in rows if "receipt_head" not in r))}

    contradictions = [k for k, v in out["records"].items() if v["class"] == "CONTRADICTION"]
    if contradictions:
        out["broken"].append(f"contradiction:{contradictions}")   # DECISION §六.1
    if out["broken"]:                                             # B5
        for v in out["records"].values():
            if v["class"] in ("FORCED_GREEN", "FORCED_ON_PARSED"):
                v["class"] = "SUPPRESSED_BY_BROKEN"
    out["bank_gate_headroom_BASERATE"] = head
    out["source_claims"] = src
    out["receipt_key_by_arm"] = receipts
    out["window_literals_found_in_R440Z"] = win_ok
    out["n_complete_tasks"] = len(pt)
    out["counts"] = {c: sum(1 for v in out["records"].values() if v["class"] == c)
                     for c in sorted({v["class"] for v in out["records"].values()})}
    out["verdict"] = "BROKEN" if out["broken"] else "CENSUS_OK"
    return out


# ──────────────────────────────────────────────────────────────────────
# 自檢
# ──────────────────────────────────────────────────────────────────────
def _fixture(mode="clean"):
    """夾具。V 與 H **不是互相導出的**（r695——夾具若把 B 從 A 導出，
    「¬V∧H 有沒有出現」這件事結構上沒有任何夾具看得見）。

    每個 mode 都是為了讓**某一個**突變體看得見而存在的；沒有夾具看得見的擋門＝空綠燈。
      clean          子集世界、零 witness、OFF 失敗率 66.7%（窗外 ⇒ 留一法必逃）
      counterexample 一列 ¬V∧H ＋ 一題不是子集（恆等式被推翻，DECISION §六.1）
      no_escape      OFF 失敗率 50%，留一法怎麼留都在窗內（⇒ UNRESOLVED）
      borderline     OFF 失敗率**剛好 60.0%（窗內）**但留一法逃得出去（給 Y4 看）
      contradiction  子集世界（恆等式成立）卻出現 ¬V∧H 的列（給 Y2 看）
      cand_only      非子集世界、witness **只在候選層**、rows 層沒有（給 Y3 看）
      unparsed       子集世界但有一題的 check 形狀認不出（給 Y1 看，B2 降級）
    """
    n = 30
    off_ok_n = {"borderline": 12, "no_escape": 15}.get(mode)
    rows = []
    for i in range(n):
        tid = f"t{i}"
        off_ok = (i < off_ok_n) if off_ok_n is not None else (i % 3 == 0)
        vis = i % 4 != 3
        hid = vis and i % 5 != 4                  # 預設 H→V（子集世界）
        if mode in ("counterexample", "contradiction") and i == 7:
            vis, hid = False, True                # ¬V ∧ H 的反例（rows 層看得見）
        rows += [
            {"task_id": tid, "arm": "OFF", "meets_demand": off_ok, "accepted": True,
             "visible_ok": off_ok, "calls_used": 1},
            {"task_id": tid, "arm": "CONFORM", "meets_demand": hid, "accepted": vis,
             "visible_ok": vis, "calls_used": 1 if vis else 5, "receipt_head": "h"},
            {"task_id": tid, "arm": "OFF5", "meets_demand": off_ok or (i % 7 == 0),
             "accepted": True, "visible_ok": True, "calls_used": 5},
        ]
    n_rej = sum(1 for r in rows if r["arm"] == "CONFORM" and not r["accepted"])
    n_bad = sum(1 for r in rows if r["arm"] == "CONFORM"
                and not r["visible_ok"] and r["meets_demand"])
    if mode == "cand_only":
        n_bad = 1                                 # 只在候選層，rows 層仍是 0
    recon = {"pz5b": {"rejected_tasks": n_rej, "all_candidates_wrong": n_rej - n_bad},
             "candidate_losslessness_EXPLORATORY": {"discarded_candidates": 40,
                                                    "discarded_but_hidden_ok": n_bad}}
    tasks = [{"task_id": f"t{i}",
              "visible_check": {"code": "__tests = ['a']"},
              "hidden_check": {"code": "__tests = ['a', 'b']"}} for i in range(n)]
    if mode in ("counterexample", "cand_only"):
        tasks[0] = {"task_id": "t0", "visible_check": {"code": "__tests = ['z']"},
                    "hidden_check": {"code": "__tests = ['a', 'b']"}}      # 不是子集
    if mode == "unparsed":
        tasks[0] = {"task_id": "t0", "visible_check": {"code": "x = f()"},
                    "hidden_check": {"code": "x = f()"}}                   # 認不出形狀
    return rows, [], tasks, recon


def selftest() -> int:
    fails = []

    def ck(name, cond, extra=""):
        if not cond:
            fails.append(f"{name} {extra}".strip())
        print(("  ok " if cond else "  FAIL ") + name + ("" if cond else f"  {extra}"))

    # 前置尺
    print("[P] 前置尺")
    ck("P0 每個窗口的字面都在 R440Z 原文裡（不是我在本檔發明的）",
       all(_windows_in_prereg(PREREG.read_text(encoding='utf-8')).values()),
       str(_windows_in_prereg(PREREG.read_text(encoding="utf-8"))))
    ck("P1 引用的原始碼運算式逐字取得到（arm_conform 的 visible_ok≡accepted）",
       not check_source_claims()["drift"], str(check_source_claims()))
    r0, c0, t0, k0 = _fixture("clean")
    vis_seq = [r["visible_ok"] for r in r0 if r["arm"] == "CONFORM"]
    hid_seq = [r["meets_demand"] for r in r0 if r["arm"] == "CONFORM"]
    ck("P2 夾具的 V 與 H 不是互相導出的（兩序列不相同、也不是彼此的否定）",
       vis_seq != hid_seq and vis_seq != [not x for x in hid_seq])
    ck("P3 夾具的子集世界裡真的沒有 ¬V∧H", not any((not v) and h
                                                    for v, h in zip(vis_seq, hid_seq)))

    print("[C] 乾淨資料")
    o = census(r0, c0, t0, recon=k0)
    ck("C1 verdict=CENSUS_OK", o["verdict"] == "CENSUS_OK", str(o["broken"]))
    ck("C2 P-Z5b 在子集世界＝FORCED_GREEN", o["records"]["P-Z5b"]["class"] == "FORCED_GREEN",
       str(o["records"]["P-Z5b"]))
    ck("C3 P-Z6 在子集世界＝FORCED_GREEN", o["records"]["P-Z6"]["class"] == "FORCED_GREEN")
    ck("C4 P-Z1（失敗率 66.7%，窗 40–60）留一法打得出窗外＝EVALUABLE",
       o["records"]["P-Z1"]["class"] == "EVALUABLE", str(o["records"]["P-Z1"]["jackknife"]))
    ck("C5a P-Z8@CONFORM：無條件字面鍵且 CONFORM 列無缺 ⇒ FORCED_GREEN",
       o["records"]["P-Z8_receipt_head@CONFORM"]["class"] == "FORCED_GREEN",
       str(o["records"]["P-Z8_receipt_head@CONFORM"]))
    ck("C5b P-Z8@ALL_ROWS：別臂的列缺鍵 ⇒ witness>0 ⇒ EVALUABLE（已為假）",
       o["records"]["P-Z8_receipt_head@ALL_ROWS"]["class"] == "EVALUABLE",
       str(o["records"]["P-Z8_receipt_head@ALL_ROWS"]["observed"]))
    ck("C5c 兩筆的母體不同 ⇒ 不准合成一筆觸發 CONTRADICTION（自檢抓到的自家坑）",
       o["records"]["P-Z8_receipt_head@CONFORM"]["population"]
       != o["records"]["P-Z8_receipt_head@ALL_ROWS"]["population"]
       and "contradiction" not in " ".join(o["broken"]))

    print("[R] 反例世界（恆等式被推翻 ⇒ DECISION §六.1 優先）")
    r1, c1, t1, k1 = _fixture("counterexample")
    o1 = census(r1, c1, t1, recon=k1)
    ck("R1 出現 ¬V∧H 的列 ⇒ P-Z6 不再是 FORCED_GREEN",
       o1["records"]["P-Z6"]["class"] != "FORCED_GREEN", str(o1["records"]["P-Z6"]))
    ck("R2 P-Z5b 的 witness 由候選層算出來（分子少一個）",
       o1["records"]["P-Z5b"]["witnesses"] > 0, str(o1["records"]["P-Z5b"]))
    ck("R3 恆等式不再成立（有一題不是子集）⇒ forced_zero False",
       o1["bank_gate_headroom_BASERATE"]["forced_zero"] is False)

    print("[W] 窗口打不出去的世界 ⇒ UNRESOLVED，不准往任何一邊倒")
    r2, c2, t2, k2 = _fixture("no_escape")
    o2 = census(r2, c2, t2, recon=k2)
    ck("W1 P-Z1 落在窗內且留一法打不出去 ⇒ UNRESOLVED",
       o2["records"]["P-Z1"]["class"] == "UNRESOLVED", str(o2["records"]["P-Z1"]["jackknife"]))

    print("[X] 每個突變體的指名夾具（沒有夾具看得見的擋門＝空綠燈）")
    rc, cc, tc, kc = _fixture("contradiction")
    oc = census(rc, cc, tc, recon=kc)
    ck("X1 Y2 的夾具：恆等式成立卻出現 ¬V∧H ⇒ CONTRADICTION（不是 FORCED_GREEN）",
       oc["records"]["P-Z6"]["class"] == "CONTRADICTION"
       and oc["verdict"] == "BROKEN", str(oc["records"]["P-Z6"]["class"]))
    rk, ckl, tk, kk = _fixture("cand_only")
    ok_ = census(rk, ckl, tk, recon=kk)
    ck("X2 Y3 的夾具：witness 只在候選層、rows 層是 0 ⇒ P-Z5b 仍 EVALUABLE",
       ok_["records"]["P-Z5b"]["witnesses"] == 1
       and ok_["records"]["P-Z5b"]["class"] == "EVALUABLE"
       and not [r for r in rk if r.get("visible_ok") is False and r.get("meets_demand")],
       str(ok_["records"]["P-Z5b"]))
    rb, cb, tb, kb = _fixture("borderline")
    ob = census(rb, cb, tb, recon=kb)
    ck("X3 Y4 的夾具：全樣本 60.0% 在窗內、留一法逃得出去 ⇒ EVALUABLE",
       abs(ob["records"]["P-Z1"]["jackknife"]["full"] - 60.0) < 1e-9
       and ob["records"]["P-Z1"]["class"] == "EVALUABLE",
       str(ob["records"]["P-Z1"]["jackknife"]))
    bogus_claim = {"bogus": ("ops/gain/gain_run.py", "arm_conform", "THIS_IS_NOT_IN_THE_SOURCE")}
    ck("X4 Y5 的夾具：釘死的字面不在原始碼裡 ⇒ 乾淨版報 drift",
       check_source_claims(bogus_claim)["drift"] == ["bogus"],
       str(check_source_claims(bogus_claim)))
    # 用真的統計量 id、只把「窗口字面」換成 R440Z 裡沒有的字串
    bogus_win = {"P-Z1": ("OFF 失敗率", (40.0, 60.0), "這串字不在 R440Z 原文裡")}
    ck("X5 Y8 的夾具：窗口字面不在 R440Z 原文裡 ⇒ 乾淨版報 window_not_in_prereg",
       any("window_not_in_prereg" in b
           for b in census(r0, c0, t0, recon=k0, windows=bogus_win)["broken"]),
       str(census(r0, c0, t0, recon=k0, windows=bogus_win)["broken"]))
    # 真 gain_run 裡沒有任何 arm_* 的 return 是「混的」⇒ any 與 all 在真原始碼上
    # 給同一個答案 ⇒ Y7 在真原始碼上**結構上沒有夾具看得見**（r706）。故餵合成原始碼。
    mixed_src = ("def arm_mixed(t):\n"
                 "    if t:\n"
                 "        return {'a': 1, 'receipt_head': 'h'}\n"
                 "    return {'a': 1}\n")
    rk2 = receipt_key_by_arm(mixed_src)
    ck("X6 Y7 的夾具：某條 return 沒有這個鍵 ⇒ 不算無條件（all 不是 any）",
       rk2["arm_mixed"]["n_returns"] == 2
       and rk2["arm_mixed"]["unconditional"] is False, str(rk2))
    ru, cu, tu, ku = _fixture("unparsed")
    ou = census(ru, cu, tu, recon=ku)
    ck("U1 Y1 的夾具：有題認不出形狀 ⇒ 降級成 FORCED_ON_PARSED（B2）",
       ou["records"]["P-Z6"]["class"] == "FORCED_ON_PARSED"
       and ou["bank_gate_headroom_BASERATE"]["n_unparsed_shape"] == 1,
       str(ou["records"]["P-Z6"]["class"]))

    print("[S] 解析度（非仲裁者，但 UNRESOLVED 沒有它就會被下一輪誤讀）")
    # 兩個世界都要**在窗內**才比得了解析度：點估計已經在窗外時距離是負的（＝證偽事件
    # 已經實現），那不是「解析度不足」。故拿 no_escape（50%，離邊界 10pp）對 borderline
    # （60.0%，貼著上緣）比。
    jr_clean = o2["records"]["P-Z1"]["jackknife"]["instrument_resolution_NOT_ARBITER"]
    jr_bord = ob["records"]["P-Z1"]["jackknife"]["instrument_resolution_NOT_ARBITER"]
    jk_clean = o2["records"]["P-Z1"]["jackknife"]
    exp_pert = max(abs(jk_clean["min"] - jk_clean["full"]),
                   abs(jk_clean["max"] - jk_clean["full"]))
    ck("S1 Y9 的夾具：擾動用的是**留一法真的動了多少**，不是拿距離冒充",
       abs((jr_clean["max_loo_perturbation"] or 0) - exp_pert) < 1e-9,
       f"got={jr_clean['max_loo_perturbation']} expected={exp_pert}")
    ck("S1b 邊界世界的比值 < 窗內有餘裕世界的比值（比值真的在動）",
       jr_bord["boundary_over_perturbation"] < jr_clean["boundary_over_perturbation"],
       f"borderline={jr_bord} clean={jr_clean}")
    ck("S2 邊界世界（60.0% 貼著上緣）比值 ≤ 1 ⇒ 留一法逃得出去，與 reachable 一致",
       jr_bord["boundary_over_perturbation"] <= 1.0
       and ob["records"]["P-Z1"]["jackknife"]["reachable"] is True, str(jr_bord))
    ck("S3 解析度欄位不改任何分類（乾淨版分類與加欄位前逐一相同）",
       o["records"]["P-Z1"]["class"] == "EVALUABLE"
       and o2["records"]["P-Z1"]["class"] == "UNRESOLVED")

    ck("V1 Y10 的夾具：一個 run 都沒掃到 ⇒ UNSCANNED，不准報成 UNRESOLVED",
       census(r0, c0, t0, runs_dir=pathlib.Path("/dev/shm/_r453_no_such_dir"),
              recon=k0)["records"]["P-Z7"]["class"] == "UNSCANNED",
       str(census(r0, c0, t0, runs_dir=pathlib.Path("/dev/shm/_r453_no_such_dir"),
                  recon=k0)["records"]["P-Z7"]))
    ck("V2 掃得到 run 時照常分類（runs_scanned 有記）",
       census(r0, c0, t0, runs_dir=ROOT / "runs",
              recon=k0)["records"]["P-Z7"]["runs_scanned"] > 0)

    print("[B] 擋門")
    o3 = census(r0[:6], c0, t0, recon=k0)
    ck("B4 完整題目 < MIN_TASKS ⇒ UNCALIBRATED 且不吐分類",
       o3["verdict"] == "UNCALIBRATED" and "records" not in o3 or not o3.get("records"),
       str(o3.get("verdict")))

    LAST_FAILS[:] = fails
    print(f"\n{'PASS' if not fails else 'FAIL'} ({len(fails)} failed)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--json")
    ap.add_argument("--runs-dir", default=None,
                    help="跨 run 找 P-Z7 的 witness；預設是 --run 的上一層")
    ap.add_argument("--bank", default="lcb2")
    ap.add_argument("--seed", default="g-r440-lcb2")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run 或 --selftest")
    d = pathlib.Path(a.run)
    # run 活著時檔案一直在長 ⇒ 先讀 bytes、從那份 bytes 解析、hash 同一份（round714 的坑）
    raw = (d / "rows.jsonl").read_bytes()
    rows = [json.loads(l) for l in raw.decode("utf-8").splitlines() if l.strip()]
    calls = [json.loads(l) for l in (d / "calls.jsonl").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    tasks = load_tasks(a.bank, summary.get("seed", a.seed), summary.get("n", a.n),
                       offset=summary.get("offset", 0))
    recon = RR.reconstruct(rows, calls, tasks)
    if recon.get("broken"):
        print(json.dumps({"verdict": "BROKEN",
                          "reason": "reject_reconstruct broken", "detail": recon["broken"][:5]},
                         ensure_ascii=False, indent=2))
        return 1
    res = census(rows, calls, tasks,
                 runs_dir=pathlib.Path(a.runs_dir) if a.runs_dir else d.parent, recon=recon)
    res["rows_lines"] = len(rows)
    res["rows_sha256_16"] = hashlib.sha256(raw).hexdigest()[:16]
    res["sampling"] = {"bank": a.bank, "seed": summary.get("seed"), "n": summary.get("n"),
                       "offset": summary.get("offset", 0)}
    res["run"] = a.run
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if a.json:
        pathlib.Path(a.json).write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return 0 if res["verdict"] in ("CENSUS_OK",) else 1


if __name__ == "__main__":
    MUTANT = __import__("os").environ.get("MUTANT", "")
    sys.exit(main())
