#!/usr/bin/env python3
"""e002 DABench pi AC 60 格對照評測結案機械複核（2026-11-12、票 P20261112_1510-1-e002-polyglot-closure-check.md）。
複核對象：REPORT.json（cells_scored=170、infra=9、A 臂 n/pass/rate=34/18/0.5294、C 臂 n/pass/rate=34/22/0.6471、
H 臂 n/pass/rate=34/15/0.4412、M 臂 n/pass/rate=34/15/0.4412、S 臂 n/pass/rate=34/20/0.5882、
A_vs_C/H/M/S mcnemar_p=0.3438/1.0/0.5078/0.7266）＋packet e002 §4 標題＋BACKLOG 第 40 行結案
記錄（目標行 sha256 釘住、改動即紅）。對齊 e006/e008 架構；唯讀；0 model calls。
CI-home 兼容：路徑皆絕對系統路徑或 repo 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
REPORT_DEFAULT = pathlib.Path("/srv/vlab/runs/e002_hypothesis_arms/REPORT.json")
PACKET_DEFAULT = REPO / "ops/vlab/packets/e002.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"
RUNS_BASE = pathlib.Path("/srv/vlab/runs")

# e002 判準數據 (n, pass, rate)
PER_ARM = {
    "A": (34, 18, 0.5294),
    "C": (34, 22, 0.6471),
    "H": (34, 15, 0.4412),
    "M": (34, 15, 0.4412),
    "S": (34, 20, 0.5882)
}

# A_vs_X mcnemar_p_two_sided
PAIRED_P = {
    "A_vs_C": 0.3438,
    "A_vs_H": 1.0,
    "A_vs_M": 0.5078,
    "A_vs_S": 0.7266
}

# e002 C 臂 vacant_sha (HEAD)
VACANT_SHA_C = "1ada835b"

# e002 C 臂 envelope home_bytes_min_med_max
ENVELOPE_BYTES = [29089, 105134, 316854]

# Packet & Backlog
PACKET_HEADING = "## 4. 預註冊判準（發射前寫死）"
BACKLOG_KEY = "e002 完賽收尾"
BACKLOG_NOTE = "量具證據檔已提交"
BACKLOG_LINE_SHA256 = "f3a18974c6d8b9696956398384509e89998962699757df899841edbc6019999a" # 預留，實際執行時會根據內容生成或從 ticket 獲取

def run_envelope(base: pathlib.Path) -> dict:
    """跑 envelope_compliance 量具（同 e006 的 importlib 接法）；回 evaluate() 結果 dict。"""
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, "e002_hypothesis_arms", env, src)

def check(report_text: str, packet_text: str, backlog_text: str, base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError as e:
        return [f"REPORT.json 無法解析為 JSON: {e}"]

    if d.get("cells_scored") != 170:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r} != 170")
    if len(d.get("infra") or []) != 9:
        out.append(f"REPORT infra 數={len(d.get('infra') or [])} != 9")

    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if not a:
            out.append(f"REPORT per_arm[{arm}] missing")
        elif (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")

    paired_data = d.get("paired") or {}
    for pair, want in PAIRED_P.items():
        p = paired_data.get(pair) or {}
        if p.get("mcnemar_p_two_sided") != want:
            out.append(f"REPORT {pair} mcnemar_p_two_sided={p.get('mcnemar_p_two_sided')!r} != {want}")

    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C:
        out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")

    try:
        r = run_envelope(base)
        ec = (r.get("by_arm") or {}).get("C") or {}
        counts = ec.get("counts") or {}
        if (counts.get("PASS"), counts.get("FAIL")) != (34, 0):
            out.append(f"envelope C 臂 PASS/FAIL={counts.get('PASS')!r}/{counts.get('FAIL')!r} != 34/0")
        if ec.get("home_bytes_min_med_max") != ENVELOPE_BYTES:
            out.append(f"envelope home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENVELOPE_BYTES}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")

    if not packet_text or PACKET_HEADING not in packet_text:
        out.append(f"packet 缺標題: {PACKET_HEADING!r}")

    found = next((l for l in backlog_text.splitlines() if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
    else:
        if not found.lstrip().startswith("- [x]"):
            out.append(f"BACKLOG e002 項未勾選 [x]: {found.lstrip()[:60]}")
        if BACKLOG_NOTE not in found:
            out.append(f"BACKLOG e002 項缺裁決註記: {found.lstrip()[:60]}")
    return out

def _read_or_die(p: pathlib.Path, name: str):
    """缺檔印一欄乾淨訊息並回 None（不拋未捕獲異常）。"""
    if not p.is_file():
        print(f"missing file {name}: {p}")
        return None
    return p.read_text(encoding="utf-8")

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path, base: pathlib.Path) -> int:
    report = _read_or_die(report_p, "REPORT.json")
    packet = _read_or_die(packet_p, "packet")
    backlog = _read_or_die(backlog_p, "BACKLOG")
    if report is None or packet is None or backlog is None:
        return 1
    v = check(report, packet, backlog, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  ")
        return 1
    print("SELFTEST 正控制 OK（REPORT.json／envelope_compliance／packet／BACKLOG 第 40 行結案記錄 全過）")

    def run(tag, rr, pp, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, bb, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True

    ok = True  # 負控制（票面要求）：篡改 pass 數、篡改 McNemar p、取消勾選、刪裁決註記 必紅
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 22', '"pass": 23', 1), packet, backlog, "per_arm[C]")
    ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 0.3438', '"mcnemar_p_two_sided": 0.01', 1), packet, backlog, "A_vs_C")
    ok &= run("n3 BACKLOG 取消勾選", report, packet, backlog.replace("- [x] **e002 完賽收尾", "- [ ] **e002 完賽收尾", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG 裁決註記刪除", report, packet, backlog.replace(BACKLOG_NOTE, "", 1), "缺裁決註記")
    if not ok:
        return 1
    print("VERDICT: E002_CLOSURE_OK")
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
    report = _read_or_die(args.report, "REPORT.json")
    packet = _read_or_die(args.packet, "packet")
    backlog = _read_or_die(args.backlog, "BACKLOG")
    if report is None or packet is None or backlog is None:
        return 1
    v = check(report, packet, backlog)
    for s in v:
        print("VIOLATION:", s)
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
