#!/usr/bin/env python3
"""smoke 初始冒煙（2 格 A/C 配對、pi 首發）完賽結案機械複核（2026-11-13、票 P20261113_0132-1）。
對齊 e002_smoke/e005 架構（含 envelope importlib 接法）；唯讀；0 model calls；純 stdlib。
複核對象（2026-11-11 常設定案第 2.b 條）：/srv/vlab/runs/smoke/REPORT.json（cells_scored=2、infra=0、A/C 各 1/1 rate=1.0、
calls 7.0/20.0、tokens 37093/151087、C vacant_sha dd2c6746…、A_vs_C pairs=1、p=1.0）＋envelope_compliance（A 臂 NA、C 臂 NO_EVIDENCE、總體 NO_EVIDENCE 誠實狀態）
＋C 格 delivery.json（mode="evidence"、deliverables=["pig_latin.py"]、in_progress=false）＋cell.json（vacant_sha dd2c6746…、task pg_pig_latin、agent pi）。
CI-home 兼容：路徑皆絕對系統路徑或 REPO 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, importlib.util, json, pathlib, shutil, tempfile
REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
EXP = "smoke"
RUN_DIR_DEFAULT = RUNS_BASE / EXP
REPORT_DEFAULT = RUN_DIR_DEFAULT / "REPORT.json"
C_CELL_DIR = "polyglot_py-pg_pig_latin-pi-C-r1"
DELIVERY_DEFAULT = next(iter(sorted(RUN_DIR_DEFAULT.glob("*-C-r1/delivery.json"))), RUN_DIR_DEFAULT / C_CELL_DIR / "delivery.json")
CELL_DEFAULT = next(iter(sorted(RUN_DIR_DEFAULT.glob("*-C-r1/cell.json"))), RUN_DIR_DEFAULT / C_CELL_DIR / "cell.json")
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"
C_VACANT_SHA = "dd2c67464eff9ba2eec478d60cf245bc601b2a57"
ARM_A = (1, 1, 1.0, 7.0, 37093, 0)   # 票面釘住 n/pass/rate/calls_per_success/tokens_per_success/timeouts
ARM_C = (1, 1, 1.0, 20.0, 151087, 0)
PAIRED_A_VS_C = (("pairs", 1), ("A_only", 0), ("C_only", 0), ("mcnemar_p_two_sided", 1.0))
ENV_ARM_A = ("NA", {"PASS": 0, "FAIL": 0, "NO_EVIDENCE": 0, "NA": 1})
ENV_ARM_C = ("NO_EVIDENCE", {"PASS": 0, "FAIL": 0, "NO_EVIDENCE": 1, "NA": 0})
def _load(text: str):
    try: return json.loads(text)
    except json.JSONDecodeError: return None
def run_envelope(base: pathlib.Path) -> dict:
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, EXP, env, src)
def check(report_text: str, delivery_text: str, cell_text: str, base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    d = _load(report_text)
    if d is None:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 2 or len(d.get("infra") or []) != 0:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r}/infra={len(d.get('infra') or [])} != 2/0")
    for arm, want in (("A", ARM_A), ("C", ARM_C)):
        a = (d.get("per_arm") or {}).get(arm) or {}
        got = (a.get("n"), a.get("pass"), a.get("rate"), a.get("calls_per_success"), a.get("tokens_per_success"), a.get("timeouts"))
        if got != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate/calls/tokens/timeouts={got!r} != {want!r}")
    c_arm = (d.get("per_arm") or {}).get("C") or {}
    if c_arm.get("vacant_sha") != [C_VACANT_SHA]:
        out.append(f"REPORT per_arm[C] vacant_sha={c_arm.get('vacant_sha')!r} != [{C_VACANT_SHA!r}]")
    pc = (d.get("paired") or {}).get("A_vs_C") or {}
    for key, want in PAIRED_A_VS_C:
        if pc.get(key) != want:
            out.append(f"REPORT A_vs_C {key}={pc.get(key)!r} != {want}")
    try:
        r = run_envelope(base)
        if (r.get("n_cells"), r.get("verdict")) != (2, "NO_EVIDENCE"):
            out.append(f"envelope n_cells/verdict={r.get('n_cells')!r}/{r.get('verdict')!r} != 2/'NO_EVIDENCE'")
        for arm, (want_v, want_c) in (("A", ENV_ARM_A), ("C", ENV_ARM_C)):
            ec = (r.get("by_arm") or {}).get(arm) or {}
            if (ec.get("verdict"), ec.get("counts")) != (want_v, want_c):
                out.append(f"envelope {arm} 臂 verdict/counts={ec.get('verdict')!r}/{ec.get('counts')!r} != {want_v!r}/{want_c!r}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    dl = _load(delivery_text)
    if dl is None:
        out.append("delivery.json 無法解析為 JSON")
    elif dl.get("mode") != "evidence":
        out.append(f"delivery mode={dl.get('mode')!r} != 'evidence'")
    elif dl.get("deliverables") != ["pig_latin.py"]:
        out.append(f"delivery deliverables={dl.get('deliverables')!r} != ['pig_latin.py']")
    elif dl.get("in_progress") is not False:
        out.append(f"delivery in_progress={dl.get('in_progress')!r} != False")
    cj = _load(cell_text)
    if cj is None:
        out.append("cell.json 無法解析為 JSON")
    else:
        for key, want in (("vacant_sha", C_VACANT_SHA), ("task", "pg_pig_latin"), ("agent", "pi")):
            if cj.get(key) != want:
                out.append(f"cell {key}={cj.get(key)!r} != {want!r}")
    return out
def make_tampered_envelope_base(work: pathlib.Path, src_run: pathlib.Path = RUN_DIR_DEFAULT) -> pathlib.Path:
    """負控制用：複製 run 目錄到臨時 base、給 C 格 cell.json 補合法 vacant_home_bytes（C 臂 NO_EVIDENCE→PASS、counts 改變）。"""
    base = work / "tampered_base"
    shutil.copytree(src_run, base / EXP)
    cj_p = base / EXP / C_CELL_DIR / "cell.json"
    cj = json.loads(cj_p.read_text(encoding="utf-8"))
    cj["vacant_home_bytes"] = 1
    cj_p.write_text(json.dumps(cj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return base
def _read_or_die(p: pathlib.Path, name: str):
    if not p.is_file():
        print(f"missing file {name}: {p}"); return None
    return p.read_text(encoding="utf-8")
def selftest(report_p, delivery_p, cell_p, base: pathlib.Path) -> int:
    report, delivery, cell = (_read_or_die(report_p, "REPORT.json"), _read_or_die(delivery_p, "delivery.json"), _read_or_die(cell_p, "cell.json"))
    if None in (report, delivery, cell): return 1
    v = check(report, delivery, cell, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  "); return 1
    print("SELFTEST 正控制 OK（REPORT.json 2 格／envelope A NA・C NO_EVIDENCE・總 NO_EVIDENCE／delivery evidence／cell 全過）")
    def _neg(tag: str, vv: list[str], must_hit: str) -> bool:  # 負控制須命中指定違規字串才算生效
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True
    with tempfile.TemporaryDirectory(prefix="smoke_closure_") as td:
        ok &= _neg("n1 REPORT cells_scored 數篡改", check(report.replace('"cells_scored": 2', '"cells_scored": 3', 1), delivery, cell, base), "cells_scored")
        ok &= _neg("n2 REPORT C 臂 vacant_sha 篡改", check(report.replace(C_VACANT_SHA, "0" * 40, 1), delivery, cell, base), "per_arm[C] vacant_sha")
        ok &= _neg("n3 envelope C 臂 NO_EVIDENCE 數篡改", check(report, delivery, cell, make_tampered_envelope_base(pathlib.Path(td), report_p.parent)), "envelope C")
        ok &= _neg("n4 delivery mode 篡改", check(report, delivery.replace('"mode": "evidence"', '"mode": "claim"', 1), cell, base), "delivery mode")
    if not ok: return 1
    print("VERDICT: SMOKE_CLOSURE_OK")
    return 0
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--delivery", type=pathlib.Path, default=DELIVERY_DEFAULT)
    ap.add_argument("--cell", type=pathlib.Path, default=CELL_DEFAULT)
    ap.add_argument("--base", type=pathlib.Path, default=RUNS_BASE, help="envelope run 目錄的 base（預設 /srv/vlab/runs）")
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.report, args.delivery, args.cell, args.base)
    report, delivery, cell = (_read_or_die(args.report, "REPORT.json"), _read_or_die(args.delivery, "delivery.json"), _read_or_die(args.cell, "cell.json"))
    if None in (report, delivery, cell): return 1
    v = check(report, delivery, cell, args.base)
    print("\n".join(f"VIOLATION: {s}" for s in v), end="")
    return 1 if v else 0
if __name__ == "__main__":
    raise SystemExit(main())
