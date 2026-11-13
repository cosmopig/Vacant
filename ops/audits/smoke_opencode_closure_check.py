#!/usr/bin/env python3
"""smoke_opencode 初始冒煙評測完賽結案機械複核（2026-11-13、票 P20261113_0041-2）。對齊 e007 架構；唯讀；0 model calls。
複核對象：REPORT.json（cells_scored=2、infra=0、A 0/1 rate=0.0、C 0/1 rate=0.0、vacant_sha dd2c6746…）＋envelope_compliance 封頂合規（C 臂 1 PASS/0 FAIL、home_bytes [119419, 119419, 119419]）
＋packet 標題＋BACKLOG 結案記錄（含 （冒煙：OpenCode 能不能在格子裡跑））。
CI-home 兼容：路徑皆絕對系統路徑或 REPO 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse, hashlib, importlib.util, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNS_BASE = pathlib.Path("/srv/vlab/runs")
EXP = "smoke_opencode"
REPORT_DEFAULT = RUNS_BASE / EXP / "REPORT.json"

# 修正 packet 路徑，支援多個可能路徑且優先考慮 REPO 下的相對路徑
PACKET_PATHS = [
    REPO / "ops/vlab/packets/smoke_opencode.md",
    REPO.parent / "ops/vlab/packets/smoke_opencode.md",
    pathlib.Path("/home/user1/dev/ops/vlab/packets/smoke_opencode.md")
]
PACKET_DEFAULT = next((p for p in PACKET_PATHS if p.is_file()), 
                       REPO / "ops/vlab/packets/smoke_opencode.md")

BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
ENV_TOOL = REPO / "ops/vlab/tools/envelope_compliance.py"

PER_ARM = {"A": (1, 0, 0.0), "C": (1, 0, 0.0)}  # n/pass/rate
VACANT_SHA_C = ["dd2c67464eff9ba2eec478d60cf245bc601b2a57"]
ENVELOPE_C_PASS_FAIL = (1, 0)
ENVELOPE_BYTES = [119419, 119419, 119419]  # C 臂 home_bytes_min_med_max
PACKET_TITLE = "# smoke_opencode · OpenCode 能不能在格子裡跑——冒煙評測（2026-11-13）"
BACKLOG_KEY = "smoke_opencode 完賽檢查"
BACKLOG_NOTE = "判定 GO"

def run_envelope(base: pathlib.Path) -> dict:
    spec = importlib.util.spec_from_file_location("envelope_compliance", ENV_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    env, src = mod._load_envelope()
    return mod.evaluate(base, EXP, env, src)

def check(report_text: str, packet_text: str, backlog_text: str,
          base: pathlib.Path = RUNS_BASE) -> list[str]:
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 2 or len(d.get("infra") or []) != 0:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r}/infra={len(d.get('infra') or [])} != 2/0")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    pc = (d.get("paired") or {}).get("A_vs_C") or {}
    for key, want in (("pairs", 1), ("A_only", 0), ("C_only", 0), ("mcnemar_p_two_sided", 1.0)):
        if pc.get(key) != want:
            out.append(f"REPORT A_vs_C {key}={pc.get(key)!r} != {want}")
    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C:
        out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")
    try:
        r = run_envelope(base)
        ec = (r.get("by_arm") or {}).get("C") or {}
        c = ec.get("counts") or {}
        if (c.get("PASS"), c.get("FAIL")) != ENVELOPE_C_PASS_FAIL:
            out.append(f"envelope C 臂 PASS/FAIL={c.get('PASS')!r}/{c.get('FAIL')!r} != {ENVELOPE_C_PASS_FAIL[0]}/{ENVELOPE_C_PASS_FAIL[1]}")
        if ec.get("home_bytes_min_med_max") != ENVELOPE_BYTES:
            out.append(f"envelope home_bytes_min_med_max={ec.get('home_bytes_min_med_max')!r} != {ENVELOPE_BYTES}")
    except (Exception, SystemExit) as e:
        out.append(f"envelope_compliance 量具不可執行: {e}")
    if not (packet_text or "").strip() or PACKET_TITLE not in packet_text:
        out.append(f"packet 缺或為空、缺標題 {PACKET_TITLE[:40]!r}…: {PACKET_DEFAULT}")
    lines = backlog_text.splitlines()
    found = next((l for l in lines if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
        return out
    if not found.lstrip().startswith("- [x]"):
        out.append(f"BACKLOG 項未勾選 [x]: {found.lstrip()[:60]}")
    if BACKLOG_NOTE not in found:
        out.append(f"BACKLOG 項缺收口註記（{BACKLOG_NOTE}）: {found.lstrip()[:60]}")
    return out

def _read_or_die(p: pathlib.Path, name: str):
    if not p.is_file():
        print(f"missing file {name}: {p}")
        return None
    return p.read_text(encoding="utf-8")

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path,
             base: pathlib.Path) -> int:
    report, packet, backlog = (_read_or_die(report_p, "REPORT.json"), _read_or_die(packet_p, "packet"), _read_or_die(backlog_p, "BACKLOG"))
    if None in (report, packet, backlog): return 1
    v = check(report, packet, backlog, base)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  "); return 1
    print("SELFTEST 正控制 OK（REPORT.json／envelope_compliance／packet／BACKLOG 結案記錄 全過）")
    def run(tag, rr, pp, bb, must_hit) -> bool:
        vv = check(rr, pp, bb, base)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 0', '"pass": 1', 1), packet, backlog, "per_arm[A]")
    ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.01', 1), packet, backlog, "A_vs_C")
    ok &= run("n3 BACKLOG 取消勾選", report, packet, backlog.replace("- [x] **smoke_opencode 完賽檢查", "- [ ] **smoke_opencode 完賽檢查", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG 收口註記刪除", report, packet, backlog.replace("判定 GO）", "）", 1), "缺收口註記")
    if not ok: return 1
    print("VERDICT: SMOKE_OPENCODE_CLOSURE_OK")
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
    if None in (report, packet, backlog): return 1
    v = check(report, packet, backlog)
    print("\n".join(f"VIOLATION: {s}" for s in v), end="")
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
