#!/usr/bin/env python3
"""e008 DABench pi AC 60 格對照評測結案機械複核（2026-11-12、票 P20261112_1326-2）。
複核對象：REPORT.json（cells_scored=60、infra=4、A 29/30 rate=0.9667、C 27/30 rate=0.9、
A_vs_C mcnemar_p=0.5、A_only=2/C_only=0、C 臂 vacant_sha）＋envelope_compliance 封頂合規
（C 臂 30 PASS/0 FAIL、home_bytes_min_med_max）＋packet e007 §5.1 標題＋BACKLOG 第 93 行結案
記錄（目標行 sha256 釘住、改動即紅）。對齊 e006/e016 架構；唯讀；0 model calls；CI-home 兼容：路徑皆絕對系統路徑或 repo 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
REPORT_DEFAULT = pathlib.Path("/srv/vlab/runs/e008_dabench_pi_AC/REPORT.json")
PACKET_DEFAULT = REPO / "ops/vlab/packets/e007_dabench.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
PER_ARM = {"A": (30, 29, 0.9667), "C": (30, 27, 0.9)}  # n/pass/rate
VACANT_SHA_C = ["9071b9f1bdfc25275bb7f1a6502205beaa4d8cad"]
ENVELOPE_BYTES = [33994, 81305, 231785]  # C 臂 home_bytes_min_med_max
PACKET_HEADING = "### 5.1 e008 full 實測結果"
BACKLOG_KEY = "e008_dabench_pi_AC 完賽收尾"
BACKLOG_NOTE = "通用任務無可測影響"
BACKLOG_LINE_SHA256 = "0bc4ff14d4a9fbaf6b071fd88f23c65288d07a1078517ced7dc1bb0ca11f2a31"

def run_envelope(base: pathlib.Path) -> dict:
    """跑 envelope_compliance 量具（同 e006 的 importlib 接法）；回 evaluate() 結果 dict。"""
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, "e008_dabench_pi_AC", env, src)

def check(report_text: str, packet_text: str, backlog_text: str, base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 60:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r} != 60")
    if len(d.get("infra") or []) != 4:
        out.append(f"REPORT infra 數={len(d.get('infra') or [])} != 4")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    pc = (d.get("paired") or {}).get("A_vs_C") or {}
    for key, want in (("mcnemar_p_two_sided", 0.5), ("A_only", 2), ("C_only", 0)):
        if pc.get(key) != want:
            out.append(f"REPORT A_vs_C {key}={pc.get(key)!r} != {want}")
    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C:
        out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")
    try:
        r = run_envelope(base)
        ec = (r.get("by_arm") or {}).get("C") or {}
        counts = ec.get("counts") or {}
        if (counts.get("PASS"), counts.get("FAIL")) != (30, 0):
            out.append(f"envelope C 臂 PASS/FAIL={counts.get('PASS')!r}/{counts.get('FAIL')!r} != 30/0")
        if ec.get("home_bytes_min_med_max") != ENVELOPE_BYTES:
            out.append(f"envelope home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENVELOPE_BYTES}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    if PACKET_HEADING not in packet_text:
        out.append(f"packet 缺標題: {PACKET_HEADING!r}")
    found = next((l for l in backlog_text.splitlines() if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
    else:
        if not found.lstrip().startswith("- [x]"):
            out.append(f"BACKLOG e008 項未勾選 [x]: {found.lstrip()[:60]}")
        if BACKLOG_NOTE not in found:
            out.append(f"BACKLOG e008 項缺裁決註記: {found.lstrip()[:60]}")
        if hashlib.sha256(found.encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
            out.append(f"BACKLOG e008 目標行 sha256 漂移（第 93 行釘住 {BACKLOG_LINE_SHA256[:12]}…、改動即紅）")
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
    print("SELFTEST 正控制 OK（REPORT.json／envelope_compliance／packet／BACKLOG 第 93 行結案記錄 全過）")
    def run(tag, rr, pp, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, bb, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True  # 負控制（票面要求）：篡改 REPORT pass 數、篡改 McNemar p、取消勾選、刪裁決註記 必紅
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 29', '"pass": 28', 1), packet, backlog, "per_arm[A]")
    ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 0.5', '"mcnemar_p_two_sided": 0.01', 1), packet, backlog, "A_vs_C")
    ok &= run("n3 BACKLOG 取消勾選", report, packet, backlog.replace("- [x] **e008_dabench_pi_AC 完賽收尾", "- [ ] **e008_dabench_pi_AC 完賽收尾", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG 裁決註記刪除", report, packet, backlog.replace(BACKLOG_NOTE, "", 1), "缺裁決註記")
    if not ok:
        return 1
    print("VERDICT: E008_CLOSURE_OK")
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
