#!/usr/bin/env python3
"""smoke_opencode 初始冒煙（2 格 A/C 配對、OpenCode 首發）完賽結案機械複核（2026-11-13、票 R20261113_0041-2）。
對齊 smoke（r1540）/e002_smoke 架構（含 envelope importlib 接法）；唯讀；0 model calls；純 stdlib。
複核對象（票面釘住）：/srv/vlab/runs/smoke_opencode/REPORT.json（cells_scored=2、infra=0、A/C 各 n=1 pass=0 rate=0.0
timeouts=0、calls/tokens null、C vacant_sha dd2c6746…、A_vs_C pairs=1、p=1.0）＋envelope_compliance（A 臂 NA、
C 臂 PASS 1/0、home_bytes_min_med_max=[119419,119419,119419]、總體 PASS）＋佇列完賽記錄
/srv/vlab/done/00_smoke_opencode.json（packet 標記「（冒煙：OpenCode 能不能在格子裡跑）」、2 格、failed_cells=0）。
CI-home 兼容：路徑皆絕對系統路徑或 REPO 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, importlib.util, json, pathlib, shutil, tempfile
REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
DONE_BASE = pathlib.Path("/srv/vlab/done")
EXP = "smoke_opencode"
RUN_DIR_DEFAULT = RUNS_BASE / EXP
REPORT_DEFAULT = RUN_DIR_DEFAULT / "REPORT.json"
DONE_DEFAULT = DONE_BASE / f"00_{EXP}.json"
C_CELL_DIR = "polyglot_py-pg_pig_latin-opencode-C-r1"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"
C_VACANT_SHA = "dd2c67464eff9ba2eec478d60cf245bc601b2a57"
PACKET_MARKER = "（冒煙：OpenCode 能不能在格子裡跑）"
ARM_A = (1, 0, 0.0, None, None, 0)   # 票面釘住 n/pass/rate/calls_per_success/tokens_per_success/timeouts
ARM_C = (1, 0, 0.0, None, None, 0)
PAIRED_A_VS_C = (("pairs", 1), ("A_only", 0), ("C_only", 0), ("mcnemar_p_two_sided", 1.0))
ENV_ARM_A = ("NA", {"PASS": 0, "FAIL": 0, "NO_EVIDENCE": 0, "NA": 1})
ENV_ARM_C = ("PASS", {"PASS": 1, "FAIL": 0, "NO_EVIDENCE": 0, "NA": 0})
ENV_C_HOME_BYTES = [119419, 119419, 119419]
OVER_CAP_BYTES = 300_000_000          # > 256 MiB 穩態封頂 268435456（負控制用）
def _load(text: str):
    try: return json.loads(text)
    except json.JSONDecodeError: return None
def run_envelope(base: pathlib.Path) -> dict:
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, EXP, env, src)
def check(report_text: str, done_text: str, base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    d = _load(report_text)
    if d is None:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("exp") != EXP:
        out.append(f"REPORT exp={d.get('exp')!r} != {EXP!r}")
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
        if (r.get("n_cells"), r.get("verdict")) != (2, "PASS"):
            out.append(f"envelope n_cells/verdict={r.get('n_cells')!r}/{r.get('verdict')!r} != 2/'PASS'")
        for arm, (want_v, want_c) in (("A", ENV_ARM_A), ("C", ENV_ARM_C)):
            ec = (r.get("by_arm") or {}).get(arm) or {}
            if (ec.get("verdict"), ec.get("counts")) != (want_v, want_c):
                out.append(f"envelope {arm} 臂 verdict/counts={ec.get('verdict')!r}/{ec.get('counts')!r} != {want_v!r}/{want_c!r}")
        ec = (r.get("by_arm") or {}).get("C") or {}
        if ec.get("home_bytes_min_med_max") != ENV_C_HOME_BYTES:
            out.append(f"envelope C 臂 home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENV_C_HOME_BYTES!r}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    q = _load(done_text)
    if q is None:
        out.append("佇列完賽記錄無法解析為 JSON")
    else:
        if q.get("exp") != EXP:
            out.append(f"done exp={q.get('exp')!r} != {EXP!r}")
        if q.get("packet") != PACKET_MARKER:
            out.append(f"done packet={q.get('packet')!r} != {PACKET_MARKER!r}")
        if len(q.get("cells") or []) != 2:
            out.append(f"done cells={len(q.get('cells') or [])} != 2")
        if q.get("failed_cells") != []:
            out.append(f"done failed_cells={q.get('failed_cells')!r} != []")
        if not q.get("finished"):
            out.append(f"done finished={q.get('finished')!r} 空")
        if q.get("vacant_sha") != C_VACANT_SHA:
            out.append(f"done vacant_sha={q.get('vacant_sha')!r} != {C_VACANT_SHA!r}")
    return out
def make_tampered_envelope_base(work: pathlib.Path, src_run: pathlib.Path = RUN_DIR_DEFAULT) -> pathlib.Path:
    """負控制用：複製 run 目錄到臨時 base、給 C 格 cell.json 補超封頂 vacant_home_bytes（C 臂 PASS→FAIL、counts 改變）。"""
    base = work / "tampered_base"
    shutil.copytree(src_run, base / EXP)
    cj_p = base / EXP / C_CELL_DIR / "cell.json"
    cj = json.loads(cj_p.read_text(encoding="utf-8"))
    cj["vacant_home_bytes"] = OVER_CAP_BYTES
    cj_p.write_text(json.dumps(cj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return base
def _read_or_die(p: pathlib.Path, name: str):
    if not p.is_file():
        print(f"missing file {name}: {p}"); return None
    return p.read_text(encoding="utf-8")
def selftest(report_p, done_p, base: pathlib.Path) -> int:
    report, done = (_read_or_die(report_p, "REPORT.json"), _read_or_die(done_p, "done record"))
    if None in (report, done): return 1
    v = check(report, done, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  "); return 1
    print("SELFTEST 正控制 OK（REPORT.json 2 格／envelope A NA・C PASS 1/0・home 119419／done 標記・2 格全過）")
    def _neg(tag: str, vv: list[str], must_hit: str) -> bool:  # 負控制須命中指定違規字串才算生效
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True
    with tempfile.TemporaryDirectory(prefix="smoke_opencode_closure_") as td:
        ok &= _neg("n1 REPORT cells_scored 數篡改", check(report.replace('"cells_scored": 2', '"cells_scored": 3', 1), done, base), "cells_scored")
        ok &= _neg("n2 REPORT C 臂 vacant_sha 篡改", check(report.replace(C_VACANT_SHA, "0" * 40, 1), done, base), "per_arm[C] vacant_sha")
        ok &= _neg("n3 envelope C 臂 PASS 數篡改", check(report, done, make_tampered_envelope_base(pathlib.Path(td), report_p.parent)), "envelope C")
        ok &= _neg("n4 佇列 packet 標記移除", check(report, done.replace(PACKET_MARKER, "已移除", 1), base), "packet")
    if not ok: return 1
    print("VERDICT: SMOKE_OPENCODE_CLOSURE_OK")
    return 0
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--done", type=pathlib.Path, default=DONE_DEFAULT)
    ap.add_argument("--base", type=pathlib.Path, default=RUNS_BASE, help="envelope run 目錄的 base（預設 /srv/vlab/runs）")
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.report, args.done, args.base)
    report, done = (_read_or_die(args.report, "REPORT.json"), _read_or_die(args.done, "done record"))
    if None in (report, done): return 1
    v = check(report, done, args.base)
    print("\n".join(f"VIOLATION: {s}" for s in v), end="")
    return 1 if v else 0
if __name__ == "__main__":
    raise SystemExit(main())
