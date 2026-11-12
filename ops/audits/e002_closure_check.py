#!/usr/bin/env python3
"""e002 Polyglot 五臂 170 格假說臂對照評測結案機械複核（2026-11-12、票 R20261112_1510-1）。
複核對象：REPORT.json（cells_scored=170、infra=9、A 18/34 rate=0.5294、C 22/34 rate=0.6471、
H/M 15/34 rate=0.4412、S 20/34 rate=0.5882、A_vs_C/H/M/S 四組配對 McNemar two-sided p、
C 臂 vacant_sha）＋packet e002.md 存在且非空＋BACKLOG 結案記錄（第 40 行、或 BACKLOG_KEY 找
目標行；須含「五臂各 34/34 完賽」與「Holm 4 組校正 p_holm 皆＝1.0」）。對齊 e006/e008 架構；
唯讀；0 model calls；CI-home 兼容：路徑皆絕對系統路徑或 repo 相對（REPO 自 __file__）、
不依賴 Path.home()。支持 --report 注入 REPORT.json 快照（預設 /srv/vlab/runs/e002_hypothesis_arms/）。"""
import argparse, json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
REPORT_DEFAULT = pathlib.Path("/srv/vlab/runs/e002_hypothesis_arms/REPORT.json")
PACKET_DEFAULT = REPO / "ops/vlab/packets/e002.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
PER_ARM = {"A": (34, 18, 0.5294), "C": (34, 22, 0.6471), "H": (34, 15, 0.4412),
           "M": (34, 15, 0.4412), "S": (34, 20, 0.5882)}  # n/pass/rate
VACANT_SHA_C = ["cf62d258d250c43fb4a40d20b9fbc2b189083e05"]
PAIRED = {  # key: (other_arm, pairs, A_only, other_only, mcnemar_p_two_sided)
    "A_vs_C": ("C", 34, 3, 7, 0.3438),
    "A_vs_H": ("H", 34, 5, 2, 0.4531),
    "A_vs_M": ("M", 34, 6, 3, 0.5078),
    "A_vs_S": ("S", 34, 3, 5, 0.7266),
}
BACKLOG_KEY = "e002 全臂最終回寫"
BACKLOG_NOTES = ("五臂各 34/34 完賽", "Holm 4 組校正 p_holm 皆＝1.0")

def check(report_text: str, packet_text: str, backlog_text: str) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 170:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r} != 170")
    if len(d.get("infra") or []) != 9:
        out.append(f"REPORT infra 數={len(d.get('infra') or [])} != 9")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    if ((d.get("per_arm") or {}).get("C") or {}).get("vacant_sha") != VACANT_SHA_C:
        out.append(f"REPORT per_arm[C].vacant_sha != {VACANT_SHA_C}")
    for key, (other, pairs, a_only, o_only, p) in PAIRED.items():
        pr = (d.get("paired") or {}).get(key) or {}
        got = (pr.get("pairs"), pr.get("A_only"), pr.get(f"{other}_only"), pr.get("mcnemar_p_two_sided"))
        if got != (pairs, a_only, o_only, p):
            out.append(f"REPORT {key} pairs/A_only/{other}_only/p={got} != {pairs}/{a_only}/{o_only}/{p}")
    if not packet_text or not packet_text.strip():
        out.append("packet e002.md 為空或純空白")
    lines = backlog_text.splitlines()
    idx = next((i for i, l in enumerate(lines) if BACKLOG_KEY in l), None)
    if idx is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
    else:
        key_line = lines[idx]
        if not key_line.lstrip().startswith("- [x]"):
            out.append(f"BACKLOG e002 項未勾選 [x]: {key_line.lstrip()[:60]}")
        block = [key_line]  # 結案記錄為多行條目：目標行＋其後的縮排續行（票面第 40 行在續行）
        for cont in lines[idx + 1:]:
            if cont.strip() and cont[:1] in (" ", "\t"):
                block.append(cont)
            else:
                break
        text = "\n".join(block)
        for note in BACKLOG_NOTES:
            if note not in text:
                out.append(f"BACKLOG e002 結案記錄缺裁決註記: {note!r}")
    return out

def _read_or_die(p: pathlib.Path, name: str):
    """缺檔印一欄乾淨訊息並回 None（不拋未捕獲異常）。"""
    if not p.is_file():
        print(f"missing file {name}: {p}")
        return None
    return p.read_text(encoding="utf-8")

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    report = _read_or_die(report_p, "REPORT.json")
    packet = _read_or_die(packet_p, "packet")
    backlog = _read_or_die(backlog_p, "BACKLOG")
    if report is None or packet is None or backlog is None:
        return 1
    v = check(report, packet, backlog)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  ")
        return 1
    print("SELFTEST 正控制 OK（REPORT.json 170 格/五臂/四組 p/C 臂 vacant_sha/packet/BACKLOG 結案記錄 全過）")
    def run(tag, rr, pp, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, bb)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True
    ok = True  # 負控制（票面要求）：篡改 REPORT pass 數、篡改 McNemar p、取消勾選、刪裁決註記 必紅
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 18', '"pass": 17', 1), packet, backlog, "per_arm[A]")
    ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 0.3438', '"mcnemar_p_two_sided": 0.01', 1), packet, backlog, "A_vs_C")
    ok &= run("n3 BACKLOG 取消勾選", report, packet, backlog.replace("- [x] **e002 全臂最終回寫", "- [ ] **e002 全臂最終回寫", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG 裁決註記刪除", report, packet, backlog.replace(BACKLOG_NOTES[1], "", 1), "缺裁決註記")
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
        return selftest(args.report, args.packet, args.backlog)
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
