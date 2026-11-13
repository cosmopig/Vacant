#!/usr/bin/env python3
"""e002 初始冒煙（e002_smoke、8 格 A/H/M/S）完賽結案機械複核（2026-11-12、票 P20261112_2332-2）。對齊 e005/e002 架構（含 envelope importlib 接法）；唯讀；0 model calls。
複核對象：REPORT.json（cells_scored=8、infra=0、A/H/S 2/2 rate=1.0、M 1/2 rate=0.5、calls/tokens per success、A_vs_H／A_vs_M／A_vs_S pairs=2、p=1.0）
＋envelope_compliance 封頂合規（無 C 臂設計、4 臂×2 格全 NA）＋packet（argon_e002_smoke_v2 或 e002.md，含 e002_smoke 標題或佇列記錄）＋BACKLOG 第 40 行結案記錄（-[x]＋收口註記＋行 sha256 釘住）。
CI-home 兼容：路徑皆絕對系統路徑或 REPO 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
EXP = "e002_smoke"
REPORT_DEFAULT = RUNS_BASE / EXP / "REPORT.json"
PACKET_DEFAULT = next((p for p in (REPO / "ops/vlab/packets/argon_e002_smoke_v2.md", REPO.parent / "ops/packets/argon_e002_smoke_v2.md",
                                   pathlib.Path("/home/user1/dev/ops/packets/argon_e002_smoke_v2.md"), REPO / "ops/vlab/packets/e002.md") if p.is_file()),
                      REPO / "ops/vlab/packets/argon_e002_smoke_v2.md")
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"
# 票面釘住：n/pass/rate/calls_per_success/tokens_per_success
PER_ARM = {"A": (2, 2, 1.0, 16.0, 200679), "H": (2, 2, 1.0, 15.0, 238169),
           "M": (2, 1, 0.5, 31.0, 328859), "S": (2, 2, 1.0, 14.0, 132555)}
PAIRED = {"A_vs_H": (("pairs", 2), ("A_only", 0), ("H_only", 0), ("mcnemar_p_two_sided", 1.0)),
          "A_vs_M": (("pairs", 2), ("A_only", 1), ("M_only", 0), ("mcnemar_p_two_sided", 1.0)),
          "A_vs_S": (("pairs", 2), ("A_only", 0), ("S_only", 0), ("mcnemar_p_two_sided", 1.0))}
ENVELOPE_ARMS = ("A", "H", "M", "S")  # 無 C 臂設計；每臂 2 格全 NA
PACKET_MARK = "e002_smoke"
BACKLOG_KEY = "e002 全臂最終回寫"
BACKLOG_NOTE = "已收口（10/30 17:0x 完賽）"
BACKLOG_LINE_NO = 40
BACKLOG_LINE_SHA256 = "439364b17d41be339fd68f381cb55caa51e1929850b6ec758b9b808a351041d5"  # 第 40 行（含行尾換行）

def run_envelope(base: pathlib.Path) -> dict:
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, EXP, env, src)

def check(report_text: str, packet_text: str, backlog_text: str, base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 8 or len(d.get("infra") or []) != 0:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r}/infra={len(d.get('infra') or [])} != 8/0")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        got = (a.get("n"), a.get("pass"), a.get("rate"), a.get("calls_per_success"), a.get("tokens_per_success"))
        if got != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate/calls/tokens={got[0]!r}/{got[1]!r}/{got[2]!r}/{got[3]!r}/{got[4]!r} != {want[0]}/{want[1]}/{want[2]}/{want[3]}/{want[4]}")
    for pk, wants in PAIRED.items():
        pc = (d.get("paired") or {}).get(pk) or {}
        for key, want in wants:
            if pc.get(key) != want:
                out.append(f"REPORT {pk} {key}={pc.get(key)!r} != {want}")
    try:
        r = run_envelope(base)
        if r.get("verdict") != "NA" or r.get("n_cells") != 8:
            out.append(f"envelope verdict/n_cells={r.get('verdict')!r}/{r.get('n_cells')!r} != 'NA'/8（無 C 臂設計、全 NA）")
        for arm in ENVELOPE_ARMS:
            ec = (r.get("by_arm") or {}).get(arm) or {}
            c = ec.get("counts") or {}
            if (ec.get("n_cells"), c.get("PASS"), c.get("FAIL"), c.get("NA"), ec.get("verdict")) != (2, 0, 0, 2, "NA"):
                out.append(f"envelope {arm} 臂 n_cells/PASS/FAIL/NA/verdict={ec.get('n_cells')!r}/{c.get('PASS')!r}/{c.get('FAIL')!r}/{c.get('NA')!r}/{ec.get('verdict')!r} != 2/0/0/2/NA")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    if not (packet_text or "").strip() or PACKET_MARK not in packet_text:
        out.append(f"packet 缺或為空、缺 {PACKET_MARK!r} 標題或佇列記錄: {PACKET_DEFAULT}")
    lines = backlog_text.splitlines()
    idx = BACKLOG_LINE_NO - 1
    found = lines[idx] if len(lines) > idx and BACKLOG_KEY in lines[idx] else next((l for l in lines if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
        return out
    if not found.lstrip().startswith("- [x]"):
        out.append(f"BACKLOG e002 收口項未勾選 [x]: {found.lstrip()[:60]}")
    if BACKLOG_NOTE not in found:
        out.append(f"BACKLOG e002 收口項缺收口註記（{BACKLOG_NOTE}）: {found.lstrip()[:60]}")
    if hashlib.sha256((found + "\n").encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
        out.append(f"BACKLOG e002 目標行 sha256 漂移（第 {BACKLOG_LINE_NO} 行釘住 {BACKLOG_LINE_SHA256[:12]}…、改動即紅）")
    return out

def _read_or_die(p: pathlib.Path, name: str):
    if not p.is_file():
        print(f"missing file {name}: {p}")
        return None
    return p.read_text(encoding="utf-8")

def selftest(report_p, packet_p, backlog_p, base: pathlib.Path) -> int:
    report, packet, backlog = (_read_or_die(report_p, "REPORT.json"), _read_or_die(packet_p, "packet"), _read_or_die(backlog_p, "BACKLOG"))
    if None in (report, packet, backlog):
        return 1
    v = check(report, packet, backlog, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  ")
        return 1
    print("SELFTEST 正控制 OK（REPORT.json 8 格／envelope_compliance 全 NA／packet／BACKLOG 第 40 行結案記錄 全過）")
    def run(tag, rr, pp, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, bb, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    i = report.index('"A_vs_M"')
    ok = True  # 負控制（票面要求）：篡改 A 臂 pass、篡改 M 臂 pass、篡改 A_vs_M McNemar p、刪 BACKLOG 註記 必紅
    ok &= run("n1 REPORT A 臂 pass 數篡改", report.replace('"pass": 2', '"pass": 1', 1), packet, backlog, "per_arm[A]")
    ok &= run("n2 REPORT M 臂 pass 數篡改", report.replace('"pass": 1', '"pass": 0', 1), packet, backlog, "per_arm[M]")
    ok &= run("n3 REPORT A_vs_M McNemar p 篡改", report[:i] + report[i:].replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.5', 1), packet, backlog, "A_vs_M mcnemar_p_two_sided")
    ok &= run("n4 BACKLOG e002 收口註記刪除", report, packet, backlog.replace(BACKLOG_NOTE, "", 1), "缺收口註記")
    if not ok:
        return 1
    print("VERDICT: E002_SMOKE_CLOSURE_OK")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.report, args.packet, args.backlog, RUNS_BASE)
    report, packet, backlog = (_read_or_die(args.report, "REPORT.json"), _read_or_die(args.packet, "packet"), _read_or_die(args.backlog, "BACKLOG"))
    if None in (report, packet, backlog):
        return 1
    v = check(report, packet, backlog)
    print("\n".join(f"VIOLATION: {s}" for s in v), end="")
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
