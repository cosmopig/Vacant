#!/usr/bin/env python3
"""R479：對 **R461 附錄 C.5／D.3／E.3** 的 10 條收官義務做可證偽性普查——零 API、純本機。

判準：`DECISION_20260905_R479_R461_APPENDIX_OBLIGATION_CENSUS.md`（工具之前的 commit）。
分類三格逐字沿用 R453 §二，**不加格**；另有兩個與 class 正交的加法式布林旗標
`executable_as_pinned`／`premise_stale`。

⚠ 本工具**不准讀主 run**（擋門 B3）。所有判斷只用「判準原文」與「被引用工具的原始碼」。
"""
from __future__ import annotations
import argparse, ast, json, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PREREG = ROOT / "DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md"
SELF_PREREG = ROOT / "DECISION_20260905_R479_R461_APPENDIX_OBLIGATION_CENSUS.md"
FORBIDDEN_RUN = "g_r461_lcb3_three_arm"                       # B3

MUTANT = os.environ.get("R479_MUTANT", "")                    # 模組層讀，import 與 __main__ 都生效
LIVE_READS = 0

# ── 被普查的 10 條。`pin` 必須在 R461 原文裡逐字找得到（B1）。
#    `probe_keys`＝義務點名的量，要在該附錄釘死的那支工具的**輸出鍵集合**裡找得到。
#    `premise`＝義務正文陳述的原始碼事實 (relpath, 字面, 必須存在?)。
TOOL_C = "ops/gain/replay/paired_ci.py"
TOOL_D = "ops/gain/r447_eq5_offline.py"
TOOL_E = "ops/gain/r447_gauge_capability.py"

CLAUSES: dict[str, dict] = {
 "C5-1": {"pin": '產物自己記的 `"key"` 欄位必須是 `"deliv"`', "tool": TOOL_C,
          "probe_keys": ["key"],
          "premise": [(TOOL_C, '"key": args.key', True)]},
 "C5-2": {"pin": '`accepted=False ∧ meets_demand=True` 的**格數**', "tool": TOOL_C,
          "probe_keys": ["accepted", "meets_demand"],
          "premise": [(TOOL_C, 'bool(r.get("accepted")) and bool(r.get("meets_demand"))', True)]},
 "D3-1": {"pin": '**產物自己記的 `sampling` 必須是', "tool": TOOL_D,
          "probe_keys": ["sampling"],
          "premise": [(TOOL_D, 'default="lcb2"', True)]},
 "D3-2": {"pin": '**`verdict` 必須是 `RECONSTRUCTED` 才准讀任何數字。**', "tool": TOOL_D,
          "probe_keys": ["verdict"],
          "premise": [(TOOL_D, 'out["rule_rates"] = {', True)]},
 "D3-3": {"pin": '**Δ 旁邊必須同時寫 `power.mde_at_n_pp` 與 `power.n_needed_for_5pp`**',
          "tool": TOOL_D, "probe_keys": ["power", "paired_gate_vs_vote"],
          "premise": [(TOOL_D, 'out["power"] = None', True)]},
 "E3-1": {"pin": '**`run_complete` 必須是 `true`（去 `summary.json` 讀，工具自己不看）。**',
          "tool": TOOL_E, "probe_keys": ["run_complete"],
          # 正文說「這支工具沒有任何完整性擋門」⇒ 這三個名字**必須不存在**，正文才還成立
          "premise": [(TOOL_E, 'BROKEN_RUN_NOT_TERMINAL', False),
                      (TOOL_E, 'BROKEN_NO_SUMMARY', False),
                      (TOOL_E, 'BROKEN_ROW_ACCOUNTING', False)]},
 "E3-2": {"pin": '**`n_tasks_complete == 189` 且 `rows_file_lines == 567`。**', "tool": TOOL_E,
          "probe_keys": ["n_tasks_complete", "rows_file_lines"],
          "premise": [(TOOL_E, '"n_tasks_complete": len(complete)', True),
                      (TOOL_E, 'out["rows_file_lines"] = len(rows)', True)]},
 "E3-3": {"pin": '**`n_tasks_partial_excluded` 要與逐臂 `infra_void` 對帳。**', "tool": TOOL_E,
          "probe_keys": ["n_tasks_partial_excluded", "infra_void"],
          "premise": [(TOOL_E, 'if len(rs) != 3', True)]},
 "E3-4": {"pin": '**判 BROKEN 要看 `verdict`，不要看有沒有數字。**', "tool": TOOL_E,
          "probe_keys": ["verdict"],
          "premise": [(TOOL_E, 'out["verdict"] = "BROKEN_BC_MISMATCH"', True)]},
 "E3-5": {"pin": '**`pz1_raw_NOT_ARBITER`／`pz1_demonstrated_only_NOT_ARBITER` 不准當成 §三 C4 的失敗率引用。**',
          "tool": TOOL_E,
          "probe_keys": ["pz1_raw_NOT_ARBITER", "pz1_demonstrated_only_NOT_ARBITER", "NOT_ARBITER"],
          "premise": [(TOOL_E, 'out["pz1_raw_NOT_ARBITER"] = fail_pct(off)', True)]},
}

# ── 事前預測（判準 §四 的表，**逐字搬過來，量測後不准改**）
PRED_CLASS = {"C5-1": "EVALUABLE", "C5-2": "EVALUABLE", "D3-1": "EVALUABLE",
              "D3-2": "EVALUABLE", "D3-3": "FORCED_GREEN", "E3-1": "EVALUABLE",
              "E3-2": "EVALUABLE", "E3-3": "UNRESOLVED", "E3-4": "EVALUABLE",
              "E3-5": "EVALUABLE"}
PRED_EXEC = {"C5-1": False, "C5-2": True, "D3-1": True, "D3-2": True, "D3-3": True,
             "E3-1": True, "E3-2": True, "E3-3": True, "E3-4": True, "E3-5": True}
PRED_STALE = {k: (k == "E3-1") for k in CLAUSES}
INTENT = {k: ("evidence" if k == "C5-2" else "guard") for k in CLAUSES}

# ── 附錄釘死的指令：(附錄字面錨點, 該指令是否帶 --json)
PINNED_CMD_ANCHORS = {TOOL_C: "ops/gain/replay/paired_ci.py --run runs/g_r461_lcb3_three_arm",
                      TOOL_D: "python3 ops/gain/r447_eq5_offline.py",
                      TOOL_E: "python3 ops/gain/r447_gauge_capability.py runs/g_r461_lcb3_three_arm"}


def _read(p: pathlib.Path) -> str:
    global LIVE_READS
    if FORBIDDEN_RUN in str(p) and "DECISION" not in p.name:
        LIVE_READS += 1                                        # B3 會抓
    return p.read_text(encoding="utf-8")


def _src(relpath: str) -> str:
    return _read(ROOT / relpath)


# ── 輸出鍵集合（ast，不用 regex 猜）
# ⚠ round750 實測：第一版只認 `out = {...}` 與 `out["k"] = ...`，**漏掉 `out.update(ev)`**
#   ⇒ 把 `r447_gauge_capability` 的 run_complete／n_tasks_complete 報成「產物裡沒有」
#   ＝型二「安靜量不到」。修法是追 update 的引數；M11 夾具把這個 bug 原樣重演。
PRODUCT_VARS = ("out", "res")
# 抽取器的雙向校準（B7）：(工具, 一定要抓到的鍵, 一定**不准**抓到的區域變數名)
KEYSCAN_CAL = {TOOL_C: ("key", "lo_pp"), TOOL_D: ("verdict", "ok_to_report"),
               TOOL_E: ("run_complete", "n_by_arm")}


def out_keys(relpath: str) -> set[str]:
    tree = ast.parse(_src(relpath))
    var_keys: dict[str, set[str]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and isinstance(n.value, ast.Dict):
                    var_keys.setdefault(t.id, set()).update(
                        k.value for k in n.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str))
                if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                        and isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str)):
                    var_keys.setdefault(t.value.id, set()).add(t.slice.value)
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and isinstance(n.value, ast.Dict):
            var_keys.setdefault(n.target.id, set()).update(
                k.value for k in n.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str))
    keys: set[str] = set()
    for v in PRODUCT_VARS:
        keys |= var_keys.get(v, set())
    if MUTANT == "M11_ignore_update":
        return keys
    for n in ast.walk(tree):                       # 追 out.update(...)／res.update(...)
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "update" and isinstance(n.func.value, ast.Name)
                and n.func.value.id in PRODUCT_VARS and n.args):
            a0 = n.args[0]
            if isinstance(a0, ast.Dict):
                keys |= {k.value for k in a0.keys
                         if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            elif isinstance(a0, ast.Name):
                keys |= var_keys.get(a0.id, set())
    return keys


def nested_keys(relpath: str) -> set[str]:
    """檔內**任意巢狀深度**的 dict 字面鍵。只拿來標註「頂層沒有、但巢狀裡有」，
    不參與 `executable_as_pinned` 的判定（判定規則在判準 §二，量測後不准改）。"""
    return {k.value for n in ast.walk(ast.parse(_src(relpath))) if isinstance(n, ast.Dict)
            for k in n.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def keyscan_calibration() -> dict:
    out = {}
    for tool, (must, must_not) in KEYSCAN_CAL.items():
        ks = out_keys(tool)
        out[tool] = {"positive": must, "positive_found": must in ks,
                     "negative": must_not, "negative_found": must_not in ks,
                     "ok": (must in ks) and (must_not not in ks)}
    out["ok"] = all(v["ok"] for v in out.values() if isinstance(v, dict))
    return out


def emits_full_product(relpath: str, prereg_text: str) -> dict:
    """義務點名的量到不到得了讀者手上：釘死的指令帶 --json，或工具把整份 out 印到 stdout。"""
    anchor = PINNED_CMD_ANCHORS[relpath]
    i = prereg_text.find(anchor)
    blk = prereg_text[i:i + 400] if i >= 0 else ""
    json_flag = "--json" in blk.split("```")[0] if blk else False
    tree = ast.parse(_src(relpath))
    dumped = {a.targets[0].id for a in ast.walk(tree)
              if isinstance(a, ast.Assign) and isinstance(a.targets[0], ast.Name)
              and isinstance(a.value, ast.Call) and ast.unparse(a.value.func) == "json.dumps"}
    prints_full = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"
                      and len(n.args) == 1
                      and ((isinstance(n.args[0], ast.Name) and n.args[0].id in dumped)
                           or (isinstance(n.args[0], ast.Call)
                               and ast.unparse(n.args[0].func) == "json.dumps"))
                      for n in ast.walk(tree))
    if MUTANT == "M7_drop_emission_check":
        return {"anchor_found": i >= 0, "pinned_has_json": True, "prints_full_json": True,
                "emitted": True}
    return {"anchor_found": i >= 0, "pinned_has_json": json_flag,
            "prints_full_json": prints_full, "emitted": bool(json_flag or prints_full)}


# ── 恆等式證明器（B5 雙向校準）
def branch_states() -> list[dict]:
    """從 `r447_eq5_offline.reconstruct` 的 `if ok_to_report:` 兩支逐字取出
    `paired_gate_vs_vote` 與 `power` 的指派，回傳每支的 (is_none, is_none) 狀態。"""
    tree = ast.parse(_src(TOOL_D))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "reconstruct")
    node = next(n for n in ast.walk(fn)
                if isinstance(n, ast.If) and ast.unparse(n.test) == "ok_to_report")
    states = []
    for body in (node.body, node.orelse):
        st = {}
        for stmt in body:
            if (isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Subscript)
                    and isinstance(stmt.targets[0].slice, ast.Constant)):
                k = stmt.targets[0].slice.value
                if k in ("paired_gate_vs_vote", "power"):
                    st[k + "_is_none"] = (isinstance(stmt.value, ast.Constant)
                                          and stmt.value.value is None)
        states.append(st)
    return states


def prove(prop: str, states: list[dict]) -> bool | None:
    if MUTANT == "M3_prover_always_true":
        return True
    if MUTANT == "M4_prover_always_false":
        return False
    if not states or any(len(s) != 2 for s in states):
        return None                                   # 取不到 ⇒ 判不出來，不准當成證明
    try:
        return all(bool(eval(prop, {"__builtins__": {}}, dict(s))) for s in states)
    except Exception:
        return None


def calibration() -> dict:
    st = branch_states()
    pos = prove("paired_gate_vs_vote_is_none == power_is_none", st)      # 已知恆真
    neg = prove("not power_is_none", st)                                 # 自由統計量，必須不是恆真
    return {"states": st, "positive_control": pos, "negative_control": neg,
            "ok": (pos is True and neg is False)}


# ── 普查本體
def census() -> dict:
    global LIVE_READS
    LIVE_READS = 0
    prereg = _read(PREREG)
    selfdoc = _read(SELF_PREREG) if SELF_PREREG.exists() else ""
    broken: list[str] = []

    pins_found, self_hits = {}, {}
    for cid, c in CLAUSES.items():
        pin = c["pin"]
        if MUTANT == "M1_pin_not_in_prereg" and cid == "E3-2":
            pin = pin + "＜這串字不在 R461 原文裡＞"
        pins_found[cid] = prereg.count(pin)
        self_hits[cid] = selfdoc.count(pin)
    if any(v == 0 for v in pins_found.values()):
        broken.append("BROKEN_PIN_NOT_IN_PREREG:" + ",".join(k for k, v in pins_found.items() if v == 0))
    if sum(self_hits.values()) != 0:
        broken.append("BROKEN_SELF_MATCH:" + ",".join(k for k, v in self_hits.items() if v))

    keysets = {t: out_keys(t) for t in (TOOL_C, TOOL_D, TOOL_E)}
    emit = {t: emits_full_product(t, prereg) for t in (TOOL_C, TOOL_D, TOOL_E)}
    kcal = keyscan_calibration()
    if not kcal["ok"]:
        broken.append("BROKEN_KEYSCAN_CALIBRATION")
    cal = calibration()
    if not cal["ok"]:
        broken.append(f'BROKEN_CALIBRATION:pos={cal["positive_control"]},neg={cal["negative_control"]}')

    recs = {}
    for cid, c in CLAUSES.items():
        tool = c["tool"]
        found = {k: (k in keysets[tool]) for k in c["probe_keys"]}
        missing = [k for k, v in found.items() if not v]
        nested_only = sorted(set(missing) & nested_keys(tool))
        execp = bool(emit[tool]["emitted"] and not missing)

        prem, stale_bits = [], []
        for relpath, lit, must in c["premise"]:
            s = _src(relpath)
            if MUTANT == "M8_premise_regex_stale" and cid == "E3-1":
                lit = lit.lower()                       # 掃不到 ⇒ 「不存在」⇒ 正文看起來沒過期
            present = lit in s
            ok = (present == must)
            prem.append({"file": relpath, "literal": lit, "must_exist": must,
                         "present": present, "premise_holds": ok})
            if not ok:
                stale_bits.append(lit)
        stale = len(stale_bits) > 0

        if cid == "D3-3":
            ident = prove("paired_gate_vs_vote_is_none == power_is_none", cal["states"])
            klass = "FORCED_GREEN" if ident is True else "UNRESOLVED"
            note = ("`power` 與 Δ 在 reconstruct 的同一個 if/else 分支被指派 ⇒ "
                    "(pgv is None)==(power is None) 窮舉兩支恆真、witness=0")
            witness = 0
        elif cid == "E3-3":
            klass, witness = "UNRESOLVED", None
            note = ("⚠ `infra_void` 頂層沒有、巢狀 `row_accounting.<臂>.infra_void` 裡有，"
                    "但那是**逐臂的整數**，給不出恆等式右邊要的**逐題集合**"
                    "（E.3 正文自己寫著 void 落在 notes.jsonl）⇒ 照釘死的指令仍量不到。 "
                    "恆等式寫得出來，但 witness 要等收官時的 infra_void 才知道，B3 禁止本輪去讀 ⇒ "
                    "嚴格規則吐 UNRESOLVED；收官必須重判（判準 §四.2）")
        else:
            klass, witness = "EVALUABLE", None
            note = "證偽事件在結果空間裡構造得出來（門檻可被違反）"

        recs[cid] = {"class": klass, "intent": INTENT[cid], "witness": witness,
                     "executable_as_pinned": execp, "premise_stale": stale,
                     "probe_keys_found": found, "probe_keys_missing": missing,
                     "probe_keys_nested_only": nested_only,
                     "emission": emit[tool], "premise_checks": prem,
                     "premise_checks_n": len(prem), "note": note,
                     "pred_class": PRED_CLASS[cid], "pred_exec": PRED_EXEC[cid],
                     "pred_stale": PRED_STALE[cid],
                     "hit_class": klass == PRED_CLASS[cid],
                     "hit_exec": execp == PRED_EXEC[cid],
                     "hit_stale": stale == PRED_STALE[cid]}

    if len(recs) == 0:
        broken.append("UNSCANNED:clauses_scanned=0")
    if any(r["premise_checks_n"] == 0 for r in recs.values()):
        broken.append("BROKEN_VACUOUS_PREMISE")          # 0 條檢查＝空綠燈，不准
    if MUTANT == "M5_read_live_run":
        _read(ROOT / "runs" / FORBIDDEN_RUN / "summary.json")
    if LIVE_READS != 0:
        broken.append(f"BROKEN_LIVE_RUN_READ:{LIVE_READS}")

    verdict = "OK" if not broken else broken[0].split(":")[0]
    return {"verdict": verdict, "broken": broken, "live_run_reads": LIVE_READS,
            "clauses_scanned": len(recs), "pins_found": pins_found,
            "self_prereg_contributed": sum(self_hits.values()),
            "calibration": cal, "keyscan_calibration": kcal, "records": recs,
            "counts": {k: sum(1 for r in recs.values() if r["class"] == k)
                       for k in ("EVALUABLE", "FORCED_GREEN", "UNRESOLVED")},
            "n_not_executable": sum(1 for r in recs.values() if not r["executable_as_pinned"]),
            "n_premise_stale": sum(1 for r in recs.values() if r["premise_stale"]),
            "pred_hits": {"class": sum(1 for r in recs.values() if r["hit_class"]),
                          "exec": sum(1 for r in recs.values() if r["hit_exec"]),
                          "stale": sum(1 for r in recs.values() if r["hit_stale"])},
            "blind": False}


FAILS: list[str] = []


def ck(name: str, cond: bool, extra: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  ' + extra) if extra else ''}")
    if not cond:
        FAILS.append(name)


def _with(mut: str):
    global MUTANT
    old, MUTANT = MUTANT, mut
    try:
        return census()
    finally:
        MUTANT = old


def selftest() -> int:
    print("[乾淨基線]")
    o = census()
    ck("A verdict==OK", o["verdict"] == "OK", str(o["broken"]))
    ck("B 掃到 10 條（UNSCANNED≠UNRESOLVED）", o["clauses_scanned"] == 10, str(o["clauses_scanned"]))
    ck("C 每條 pin 都在 R461 原文裡", all(v > 0 for v in o["pins_found"].values()))
    ck("D 本判準檔自己貢獻 0 條（B6 防自我匹配）", o["self_prereg_contributed"] == 0)
    ck("E live_run_reads==0（B3）", o["live_run_reads"] == 0)
    ck("F 雙向校準：正對照 True／負對照 False",
       o["calibration"]["positive_control"] is True and o["calibration"]["negative_control"] is False,
       f'pos={o["calibration"]["positive_control"]} neg={o["calibration"]["negative_control"]}')
    ck("G 每條至少 1 個 premise 檢查（不准空綠燈）",
       all(r["premise_checks_n"] >= 1 for r in o["records"].values()))

    ck("H 鍵抽取器雙向校準（正：抓得到產物鍵／負：抓不到區域變數）",
       o["keyscan_calibration"]["ok"], json.dumps(
           {t.split("/")[-1]: v["ok"] for t, v in o["keyscan_calibration"].items()
            if isinstance(v, dict)}))

    print("[植入缺陷：判準＝該吐哪個字串／哪個量要變，不是只看 rc]")
    m1 = _with("M1_pin_not_in_prereg")
    ck("M1 pin 字面改掉 ⇒ BROKEN_PIN_NOT_IN_PREREG", m1["verdict"] == "BROKEN_PIN_NOT_IN_PREREG",
       str(m1["broken"]))
    m3 = _with("M3_prover_always_true")
    ck("M3 證明器恆真 ⇒ 負對照失守 ⇒ BROKEN_CALIBRATION",
       m3["verdict"] == "BROKEN_CALIBRATION", str(m3["broken"]))
    m4 = _with("M4_prover_always_false")
    ck("M4 證明器恆假 ⇒ 正對照失守 ⇒ BROKEN_CALIBRATION",
       m4["verdict"] == "BROKEN_CALIBRATION", str(m4["broken"]))
    m5 = _with("M5_read_live_run")
    ck("M5 讀主 run ⇒ BROKEN_LIVE_RUN_READ 且 live_run_reads>0",
       m5["verdict"] == "BROKEN_LIVE_RUN_READ" and m5["live_run_reads"] > 0,
       str(m5["live_run_reads"]))
    m7 = _with("M7_drop_emission_check")
    ck("M7 拿掉「產物到不到得了手上」⇒ C5-1 的缺陷消失（n_not_executable 掉下來）",
       m7["records"]["C5-1"]["executable_as_pinned"] is True
       and m7["n_not_executable"] < o["n_not_executable"],
       f'{o["n_not_executable"]} -> {m7["n_not_executable"]}')
    m8 = _with("M8_premise_regex_stale")
    ck("M8 premise 字面掃不到 ⇒ E3-1 的過期消失（安靜量不到也要看得見）",
       m8["records"]["E3-1"]["premise_stale"] is False and m8["n_premise_stale"] == 0,
       f'{o["n_premise_stale"]} -> {m8["n_premise_stale"]}')

    m11 = _with("M11_ignore_update")
    ck("M11 不追 out.update(...) ⇒ 型二安靜量不到（run_complete 從產物鍵集合消失）",
       (m11["records"]["E3-1"]["probe_keys_missing"] == ["run_complete"]
        and m11["n_not_executable"] > o["n_not_executable"]
        and m11["verdict"] == "BROKEN_KEYSCAN_CALIBRATION"),
       f'not_exec {o["n_not_executable"]} -> {m11["n_not_executable"]}, verdict={m11["verdict"]}')

    print("[承重牆：實體刪掉，不是 env 旗標]")
    # 只取「census 本體」那一段原始碼（切在 selftest 之前），避免自我匹配到本函式的字串字面
    full = _src("ops/gain/r479_r461_appendix_census.py")
    cut = "FAI" + "LS: list[str] = []"
    ck("M8b 切點在原始碼裡恰好出現一次（夾具不准過期）", full.count(cut) == 1, str(full.count(cut)))
    src = full.split(cut)[0]
    seg = '    if len(recs) == 0:\n        broken.append("UNSCANNED:clauses_scanned=0")\n'
    ck("M9 UNSCANNED 那段在原始碼裡逐字存在（不存在＝夾具過期，不是通過）", seg in src)
    blind = "recs = {}"
    ns: dict = {"__file__": __file__}
    exec(compile(src.replace(seg, "").replace(blind, blind + "\n    CLAUSES.clear()"),
                 "<M9>", "exec"), ns)
    m9 = ns["census"]()
    ck("M9 刪掉 UNSCANNED 擋門 ＋ 掃到 0 條 ⇒ 不再叫（verdict 不是 UNSCANNED）",
       m9["clauses_scanned"] == 0 and m9["verdict"] != "UNSCANNED", m9["verdict"])
    ns2: dict = {"__file__": __file__}
    exec(compile(src.replace(blind, blind + "\n    CLAUSES.clear()"), "<M10>", "exec"), ns2)
    m10 = ns2["census"]()
    ck("M10 只清空目標、擋門留著 ⇒ UNSCANNED（＝M9 的正對照）",
       m10["clauses_scanned"] == 0 and m10["verdict"] == "UNSCANNED", m10["verdict"])

    print(f"\nselftest {'SELFTEST_PASS' if not FAILS else 'SELFTEST_FAIL ' + ','.join(FAILS)} "
          f"{len(FAILS)} fail")
    return 1 if FAILS else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    o = census()
    print(f'verdict {o["verdict"]}  rc={0 if o["verdict"] == "OK" else 2}  '
          f'clauses={o["clauses_scanned"]}  live_run_reads={o["live_run_reads"]}')
    print(f'  counts={o["counts"]}  not_executable={o["n_not_executable"]}  '
          f'premise_stale={o["n_premise_stale"]}')
    print(f'  事前預測命中 class={o["pred_hits"]["class"]}/10  exec={o["pred_hits"]["exec"]}/10  '
          f'stale={o["pred_hits"]["stale"]}/10   （blind=False，見判準 §〇.2）')
    for cid, r in o["records"].items():
        flag = ("  ⚠不可執行" if not r["executable_as_pinned"] else "") + \
               ("  ⚠正文過期" if r["premise_stale"] else "")
        miss = "".join(x for x, h in (("class", r["hit_class"]), ("exec", r["hit_exec"]),
                                      ("stale", r["hit_stale"])) if not h)
        print(f'  {cid:5s} {r["class"]:12s} intent={r["intent"]:8s}{flag}'
              + (f'   MISS:{miss}' if miss else ""))
    if a.json:
        pathlib.Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.json).write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if o["verdict"] == "OK" else 2


if __name__ == "__main__":
    sys.exit(main())
