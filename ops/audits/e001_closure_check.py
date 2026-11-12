#!/usr/bin/env python3
"""e001 Pi AC Baseline 120 格基準評測結案機械複核（2026-11-12、票 P20261112_1528-2）。
複核：REPORT.json（cells_scored=120、infra=14、A 28/60 rate=0.4667、C 34/60 rate=0.5667、
A_vs_C p=0.1094、A_only=2/C_only=8、C 臂 vacant_sha）＋envelope_compliance 封頂合規（C 臂 60 PASS/0 FAIL、
home_bytes_min_med_max）＋packet e001 標題＋審計報告（Total Cells Scored / McNemar p）＋BACKLOG 第 16 行
e001 執行樹身分錨（行 sha256 釘住、改動即紅）。對齊 e008 架構；唯讀；0 model calls；CI-home 兼容：
REPO 自 __file__／簿記目錄候選、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
REPORT_DEFAULT = RUNS_BASE / "e001_pi_AC_baseline/REPORT.json"
PACKET_DEFAULT = REPO / "ops/vlab/packets/e001.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"
PER_ARM = {"A": (60, 28, 0.4667), "C": (60, 34, 0.5667)}  # n/pass/rate
VACANT_SHA_C = ["dd2c67464eff9ba2eec478d60cf245bc601b2a57"]
PAIRED_AVS_C = {"pairs": 60, "A_only": 2, "C_only": 8, "mcnemar_p_two_sided": 0.1094}
ENVELOPE_BYTES = [27611, 333481, 1146648]  # C 臂 home_bytes_min_med_max
PACKET_HEADING = "# e001：pi 裝 vs 沒裝 Vacant 的真實基線"
AUDIT_NEEDLES = ("Total Cells Scored: 120", "McNemar exact two-sided p=0.1094")
BACKLOG_KEY = "e001 執行樹"
BACKLOG_LINE_SHA256 = "b71e9f07bc5a3c6d26a1953e6a8cccfc5d5ff89fe61b9089990cd56bd4b040b8"


def audit_default() -> pathlib.Path:
    """審計報告在簿記目錄；repo 路徑在位優先，否則候選（e009 口徑＋本機實體簿記目錄）。"""
    cands = (REPO / "ops/audits/e001_pi_AC_baseline.md", REPO.parent / "ops/audits/e001_pi_AC_baseline.md", pathlib.Path("/home/user1/dev/ops/audits/e001_pi_AC_baseline.md"))
    return next((p for p in cands if p.is_file()), cands[0])


def run_envelope(base: pathlib.Path) -> dict:
    """跑 envelope_compliance 量具（同 e008 的 importlib 接法）；回 evaluate() 結果 dict。"""
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, "e001_pi_AC_baseline", env, src)


def check(report_text: str, packet_text: str, audit_text: str, backlog_text: str, base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 120:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r} != 120")
    if len(d.get("infra") or []) != 14:
        out.append(f"REPORT infra 數={len(d.get('infra') or [])} != 14")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C:
        out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")
    pc = (d.get("paired") or {}).get("A_vs_C") or {}
    for key, want in PAIRED_AVS_C.items():
        if pc.get(key) != want:
            out.append(f"REPORT A_vs_C {key}={pc.get(key)!r} != {want}")
    try:
        r = run_envelope(base)
        ec = (r.get("by_arm") or {}).get("C") or {}
        counts = ec.get("counts") or {}
        if (counts.get("PASS"), counts.get("FAIL")) != (60, 0):
            out.append(f"envelope C 臂 PASS/FAIL={counts.get('PASS')!r}/{counts.get('FAIL')!r} != 60/0")
        if ec.get("home_bytes_min_med_max") != ENVELOPE_BYTES:
            out.append(f"envelope home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENVELOPE_BYTES}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    if PACKET_HEADING not in packet_text:
        out.append(f"packet 缺標題: {PACKET_HEADING!r}")
    flat = audit_text.replace("*", "")  # 審計報告 markdown 粗體 **...** 對判準透明
    for needle in AUDIT_NEEDLES:
        if needle not in flat:
            out.append(f"審計報告缺關聯字: {needle!r}")
    found = next((l for l in backlog_text.splitlines() if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
    elif hashlib.sha256(found.encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
        out.append(f"BACKLOG e001 執行樹目標行 sha256 漂移（第 16 行釘住 {BACKLOG_LINE_SHA256[:12]}…、改動即紅）")
    return out


def _read_or_die(p: pathlib.Path, name: str):
    """缺檔印一欄乾淨訊息並回 None（不拋未捕獲異常）。"""
    if not p.is_file():
        print(f"missing file {name}: {p}")
        return None
    return p.read_text(encoding="utf-8")


def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, audit_p: pathlib.Path, backlog_p: pathlib.Path, base: pathlib.Path) -> int:
    texts = [_read_or_die(p, n) for p, n in ((report_p, "REPORT.json"), (packet_p, "packet"), (audit_p, "審計報告"), (backlog_p, "BACKLOG"))]
    if None in texts:
        return 1
    report, packet, audit, backlog = texts
    v = check(report, packet, audit, backlog, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  ")
        return 1
    print("SELFTEST 正控制 OK（REPORT.json／envelope_compliance／packet／審計報告／BACKLOG 第 16 行 全過）")
    def run(tag, rr, pp, aa, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, aa, bb, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True  # 負控制（票面要求）：篡改 REPORT pass 數、篡改 McNemar p、篡改封包標題、刪審計報告關聯字 必紅
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 28', '"pass": 27', 1), packet, audit, backlog, "per_arm[A]")
    ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 0.1094', '"mcnemar_p_two_sided": 0.05', 1), packet, audit, backlog, "A_vs_C")
    ok &= run("n3 封包標題篡改", report, packet.replace("裝 vs 沒裝", "裝 X 沒裝", 1), audit, backlog, "packet 缺標題")
    ok &= run("n4 審計報告關聯字刪除", report, packet, audit.replace("p=0.1094", "p=0.9999", 1), backlog, "審計報告缺關聯字")
    if not ok:
        return 1
    print("VERDICT: E001_CLOSURE_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--audit", type=pathlib.Path, default=audit_default())
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.report, a.packet, a.audit, a.backlog, RUNS_BASE)
    texts = [_read_or_die(p, n) for p, n in ((a.report, "REPORT.json"), (a.packet, "packet"), (a.audit, "審計報告"), (a.backlog, "BACKLOG"))]
    if None in texts:
        return 1
    v = check(*texts)
    for s in v:
        print("VIOLATION:", s)
    return 1 if v else 0


if __name__ == "__main__":
    raise SystemExit(main())
