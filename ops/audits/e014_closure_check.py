#!/usr/bin/env python3
"""e014 DABStep 阻擋級機制實驗結案機械複核（票 P20261112_1125-1；0 model calls、只讀）。證據：REPORT.json（78/78、infra=[]、A 13/26、C 14/26、CB 14/26、A_vs_C/A_vs_CB
McNemar p=1.0、CB.pass==C.pass、CB/A calls 0.522×/tokens 0.501× 皆 <2× 紅線）；packet 非空；BACKLOG 第 14 行 `- [x] **e014 完賽`＋
「H1（blocking>evidence）在 DABStep 被否」（~/dev/ops 鏡像 byte 一致）。對齊 e016/e004（含 e004 selftest missing-file 預檢）：
REPO 自 __file__ 推導、CI-home 相容；REPORT 在 repo 外、以 --report 注入快照；BACKLOG 接受目標行 sha fallback。"""
import argparse
import hashlib
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
REPORT_DEFAULT = pathlib.Path("/srv/vlab/runs/e014_dabstep_block/REPORT.json")
PACKET_DEFAULT = REPO / "ops/vlab/packets/e014_dabstep_block.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
REPORT_SHA256 = "d71bc47ee36687f0d1a059ae57349fa4b1e528faafefff3639898222241b6e3f"
PACKET_SHA256 = "490c4021b478357d58328d5945db0afa768c9b998073d5dc039099255ce25d3b"
BACKLOG_SHA256 = "d541af4d317c2462a80d1aeee34d0c2ae5dcd047fde227901f0f30ecf7355fe9"
BACKLOG_LINE_NO = 14
BACKLOG_LINE_SHA256 = "c19b4cef2837fbc0c555990fda2fcc27bdcbb089a8cb7f0b0ccb99c6b1b0c83a"
BACKLOG_KEY = "e014 完賽（round 894 裁決"
BACKLOG_VERDICT = "H1（blocking>evidence）在 DABStep 被否"
PINS = {REPORT_DEFAULT: REPORT_SHA256, PACKET_DEFAULT: PACKET_SHA256, BACKLOG_DEFAULT: BACKLOG_SHA256}

def check(report_text: str, packet_text: str, backlog_text: str) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT json 無法解析"]
    out: list[str] = []
    if d.get("cells_scored") != 78:
        out.append(f"cells_scored={d.get('cells_scored')!r} != 78")
    if d.get("infra") != []:
        out.append(f"infra={d.get('infra')!r} != []")
    arms = d.get("per_arm", {})
    for arm, want in (("A", (26, 13, 0.5)), ("C", (26, 14, 0.5385)), ("CB", (26, 14, 0.5385))):
        a = arms.get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    for key in ("A_vs_C", "A_vs_CB"):
        p = (d.get("paired", {}) or {}).get(key) or {}
        if p.get("mcnemar_p_two_sided") != 1.0:
            out.append(f"paired[{key}].mcnemar_p_two_sided={p.get('mcnemar_p_two_sided')!r} != 1.0")
    cb, cc, ca = arms.get("CB") or {}, arms.get("C") or {}, arms.get("A") or {}
    if cb.get("pass") != cc.get("pass"):
        out.append(f"CB vs C 零分歧對必要條件違反：pass CB={cb.get('pass')!r} != C={cc.get('pass')!r}")
    for k in ("calls_per_success", "tokens_per_success"):
        if not (cb.get(k) and ca.get(k)):
            out.append(f"成本 {k} 缺值（CB/A）")
        elif not 0 < cb[k] / ca[k] < 2.0:
            out.append(f"成本紅線 CB/A {k}={cb[k] / ca[k]:.3f} 未 < 2.0")
    if not packet_text.strip():
        out.append("packet 為空")
    lines = backlog_text.splitlines()
    if len(lines) < BACKLOG_LINE_NO:
        out.append(f"BACKLOG 少於 {BACKLOG_LINE_NO} 行")
        return out
    ln = lines[BACKLOG_LINE_NO - 1]
    if not ln.lstrip().startswith("- [x]"):
        out.append(f"BACKLOG 第 {BACKLOG_LINE_NO} 行未勾選 [x]: {ln.lstrip()[:48]}")
    if BACKLOG_KEY not in ln:
        out.append(f"BACKLOG 第 {BACKLOG_LINE_NO} 行缺 e014 完賽項")
    if BACKLOG_VERDICT not in ln:
        out.append(f"BACKLOG 第 {BACKLOG_LINE_NO} 行缺裁決註記（H1 在 DABStep 被否）")
    return out

def check_snapshot(p: pathlib.Path, want: str) -> list[str]:
    """凍結快照須存在且 sha256 與釘住值一致（BACKLOG 為共用檔，接受目標行 sha256 相符）。"""
    if not p.is_file():
        return [f"snapshot missing: {p}"]
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() == want:
        return []
    if want == BACKLOG_SHA256:
        lines = raw.decode("utf-8", errors="replace").splitlines()
        if len(lines) >= BACKLOG_LINE_NO and hashlib.sha256(
                lines[BACKLOG_LINE_NO - 1].encode("utf-8")).hexdigest() == BACKLOG_LINE_SHA256:
            return []
    return [f"snapshot sha256 drift {p.name}: {hashlib.sha256(raw).hexdigest()[:12]}… != 釘住 {want[:12]}…（凍結紀錄，改動即紅）"]

def _pinned(p: pathlib.Path) -> list[str]:
    """只有缺省快照受釘住；以 --report/--packet/--backlog 明確覆蓋時不釘（內容判準照跑）。"""
    return check_snapshot(p, PINS[p]) if p in PINS else []

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    missing = [f"SELFTEST missing file {n}: {p}" for n, p in (("REPORT.json", report_p), ("packet", packet_p), ("BACKLOG", backlog_p)) if not p.is_file()]
    if missing:
        print(*missing, sep="\n")
        return 1
    r = report_p.read_text(encoding="utf-8")
    p = packet_p.read_text(encoding="utf-8")
    b = backlog_p.read_text(encoding="utf-8")
    v = check(r, p, b) + _pinned(report_p) + _pinned(packet_p) + _pinned(backlog_p)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:\n" + "\n".join("  " + s for s in v)); return 1
    def run(tag: str, rr: str, pp: str, bb: str, must_hit: str) -> bool:
        vv = check(rr, pp, bb)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = run("n1 REPORT pass 數", r.replace('"pass": 13', '"pass": 12', 1), p, b, "pass")
    ok &= run("n2 McNemar p", r.replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.05', 1), p, b, "mcnemar")
    ok &= run("n3 BACKLOG 未勾選", r, p, b.replace("- [x] **e014 完賽（round 894 裁決", "- [ ] **e014 完賽（round 894 裁決", 1), "未勾選 [x]")
    ok &= run("n4 裁決註記", r, p, b.replace(BACKLOG_VERDICT, "H1（blocking>evidence）待裁決", 1), "裁決註記")
    if not ok:
        return 1
    print("VERDICT: E014_CLOSURE_OK")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制")
    ap.add_argument("--report", type=pathlib.Path, default=REPORT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.report, args.packet, args.backlog)
    v = check(args.report.read_text(encoding="utf-8"),
              args.packet.read_text(encoding="utf-8"),
              args.backlog.read_text(encoding="utf-8"))
    v += _pinned(args.report) + _pinned(args.packet) + _pinned(args.backlog)
    if v:
        print("\n".join(v))
    print("VERDICT: " + ("E014_CLOSURE_OK" if not v else "E014_CLOSURE_FAIL"))
    return 0 if not v else 1

if __name__ == "__main__":
    raise SystemExit(main())
