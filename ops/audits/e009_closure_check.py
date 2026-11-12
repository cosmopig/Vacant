#!/usr/bin/env python3
"""e009 e002 A/C 第二次重複（68 格）完賽結案機械複核（2026-11-12、票 P20261112_1528-1）。對齊 e006/e008 架構；唯讀；0 model calls。
複核對象：REPORT.json（cells_scored=67、infra=41、A 17/34 rate=0.5、C 18/33 rate=0.5455、A_vs_C mcnemar_p=1.0、
A_only=3/C_only=4、C 臂 vacant_sha）＋envelope_compliance 封頂合規（C 臂 33 PASS/0 FAIL、home_bytes_min_med_max）
＋packet 標題＋l2c1.json（若在位則核對、L2-C1 NOT_MET）＋BACKLOG 第 56 行結案記錄（-[x]＋
L2-C1 NOT_MET（抽樣差）、撤案＋選項 0（不改產品）＋目標行 sha256 釘住、改動即紅）。CI-home 兼容：
路徑皆絕對系統路徑或 repo 相對（REPO 自 __file__、簿記目錄＝REPO.parent/ops）、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
EXP = "e009_replicate_e002_AC"
REPORT_DEFAULT = RUNS_BASE / EXP / "REPORT.json"

def _first(*c):
    return next((p for p in c if p.is_file()), c[0])

PACKET_DEFAULT = _first(REPO / "ops/packets/e009_replicate_e002_AC.md", REPO.parent / "ops/packets/e009_replicate_e002_AC.md", pathlib.Path("/home/user1/dev/ops/packets/e009_replicate_e002_AC.md"))
L2C1_DEFAULT = _first(REPO / "ops/audits/e009_outputs/l2c1.json", REPO.parent / "ops/audits/e009_outputs/l2c1.json", pathlib.Path("/home/user1/dev/ops/audits/e009_outputs/l2c1.json"))
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"
PER_ARM = {"A": (34, 17, 0.5), "C": (33, 18, 0.5455)}  # n/pass/rate
VACANT_SHA_C = ["cf62d258d250c43fb4a40d20b9fbc2b189083e05"]
ENVELOPE_BYTES = [14856, 74081, 393813]  # C 臂 home_bytes_min_med_max
PACKET_TITLE = "# e009：e002 的 A／C 第二次重複"
BACKLOG_KEY = "e009_replicate_e002_AC 完賽收尾"
BACKLOG_NOTE = "L2-C1 NOT_MET（抽樣差）、撤案"
BACKLOG_OPT0 = "選項 0（不改產品）"
BACKLOG_LINE_SHA256 = "5f27f75990fd3193c93dce945cc17f4566fb86ebef22123f5f0a2e74acddb5ac"

def run_envelope(base: pathlib.Path) -> dict:
    """跑 envelope_compliance 量具（同 e006 的 importlib 接法）；回 evaluate() 結果 dict。"""
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, EXP, env, src)

def check(report_text: str, packet_text: str, backlog_text: str,
          l2c1_text: str | None = None, base: pathlib.Path = RUNS_BASE) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。l2c1_text=None＝跳過（若在位則核對）。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 67 or len(d.get("infra") or []) != 41:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r}/infra={len(d.get('infra') or [])} != 67/41")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    pc = (d.get("paired") or {}).get("A_vs_C") or {}
    for key, want in (("pairs", 33), ("A_only", 3), ("C_only", 4), ("mcnemar_p_two_sided", 1.0)):
        if pc.get(key) != want:
            out.append(f"REPORT A_vs_C {key}={pc.get(key)!r} != {want}")
    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C:
        out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")
    try:
        r = run_envelope(base)
        ec = (r.get("by_arm") or {}).get("C") or {}
        c = ec.get("counts") or {}
        if (c.get("PASS"), c.get("FAIL")) != (33, 0):
            out.append(f"envelope C 臂 PASS/FAIL={c.get('PASS')!r}/{c.get('FAIL')!r} != 33/0")
        if ec.get("home_bytes_min_med_max") != ENVELOPE_BYTES:
            out.append(f"envelope home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENVELOPE_BYTES}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    if not (packet_text or "").strip() or PACKET_TITLE not in packet_text:
        out.append(f"packet 缺或為空、缺標題 {PACKET_TITLE!r}: {PACKET_DEFAULT}")
    if l2c1_text is not None and ("L2-C1" not in l2c1_text or "NOT_MET" not in l2c1_text):
        out.append("l2c1.json 缺 L2-C1 NOT_MET（若在位則核對）")
    lines = backlog_text.splitlines()
    found = lines[55] if len(lines) >= 56 and BACKLOG_KEY in lines[55] else next((l for l in lines if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
        return out
    if not found.lstrip().startswith("- [x]"):
        out.append(f"BACKLOG e009 項未勾選 [x]: {found.lstrip()[:60]}")
    for note in (BACKLOG_NOTE, BACKLOG_OPT0):
        if note not in found:
            out.append(f"BACKLOG e009 項缺裁決註記（{note}）: {found.lstrip()[:60]}")
    if hashlib.sha256(found.encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
        out.append(f"BACKLOG e009 目標行 sha256 漂移（第 56 行釘住 {BACKLOG_LINE_SHA256[:12]}…、改動即紅）")
    return out

def _read_or_die(p: pathlib.Path, name: str):
    """缺檔印一欄乾淨訊息並回 None（不拋未捕獲異常）。"""
    if not p.is_file():
        print(f"missing file {name}: {p}")
        return None
    return p.read_text(encoding="utf-8")

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path,
             l2c1_p: pathlib.Path, base: pathlib.Path) -> int:
    report, packet, backlog = (_read_or_die(report_p, "REPORT.json"), _read_or_die(packet_p, "packet"), _read_or_die(backlog_p, "BACKLOG"))
    if None in (report, packet, backlog):
        return 1
    l2c1 = l2c1_p.read_text(encoding="utf-8") if (l2c1_p is not None and l2c1_p.is_file()) else None
    v = check(report, packet, backlog, l2c1, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  ")
        return 1
    print("SELFTEST 正控制 OK（REPORT.json／envelope_compliance／packet／l2c1／BACKLOG 第 56 行結案記錄 全過）")
    def run(tag, rr, pp, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, bb, l2c1, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True  # 負控制（票面要求）：篡改 REPORT pass 數、篡改 McNemar p、取消勾選、刪裁決註記 必紅
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 17', '"pass": 16', 1), packet, backlog, "per_arm[A]")
    ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.01', 1), packet, backlog, "A_vs_C")
    ok &= run("n3 BACKLOG 取消勾選", report, packet, backlog.replace("- [x] **e009_replicate_e002_AC 完賽收尾", "- [ ] **e009_replicate_e002_AC 完賽收尾", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG 裁決註記刪除", report, packet, backlog.replace(BACKLOG_NOTE, "", 1), "缺裁決註記")
    if not ok:
        return 1
    print("VERDICT: E009_CLOSURE_OK")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    ap.add_argument("--l2c1", type=pathlib.Path, default=L2C1_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.report, args.packet, args.backlog, args.l2c1, RUNS_BASE)
    report, packet, backlog = (_read_or_die(args.report, "REPORT.json"), _read_or_die(args.packet, "packet"), _read_or_die(args.backlog, "BACKLOG"))
    if None in (report, packet, backlog):
        return 1
    l2c1 = args.l2c1.read_text(encoding="utf-8") if args.l2c1.is_file() else None
    v = check(report, packet, backlog, l2c1)
    print("\n".join(f"VIOLATION: {s}" for s in v), end="")
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
