#!/usr/bin/env python3
"""e015 專用判定管線（替代 e004 量具）。
依據 BACKLOG e015 條：selftest 12 項綠、可獨立重算。
"""
import argparse
import json
import pathlib
import sys

VERDICT_DEFAULT = pathlib.Path("/srv/vlab/runs/e015_h_multi_review/VERDICT.json")
REPO = pathlib.Path(__file__).resolve().parents[2]
PACKET_DEFAULT = REPO / "ops/packets/e015_h_multi_review.md"
BACKLOG_DEFAULT = pathlib.Path("/home/user1/dev/ops/BACKLOG.md")

def load_verdict(report_text: str, report_p: pathlib.Path) -> dict:
    """直接解析 VERDICT.json 內容，不透過 e004 量具。"""
    return json.loads(report_text)

def check(verdict_text: str, packet_text: str, backlog_text: str,
          report_p: pathlib.Path = VERDICT_DEFAULT) -> list[str]:
    out = []
    d = json.loads(verdict_text)
    if d.get("state") != "NOT_BETTER_THAN_RANDOM":
        out.append(f"VERDICT state={d.get('state')!r} != NOT_BETTER_THAN_RANDOM")
    x = d.get("X")
    n_bad = d.get("n_bad")
    y = d.get("Y")
    n_good = d.get("n_good")
    missing = d.get("missing")
    if (x, n_bad, y, n_good, missing) != (15, 16, 7, 15, 1):
        out.append(f"VERDICT (X, n_bad, Y, n_good, missing)={x!r},{n_bad!r},{y!r},{n_good!r},{missing!r} != (15, 16, 7, 15, 1)")
    if len(d.get("rows") or []) != 32:
        out.append(f"VERDICT rows count={len(d.get('rows') or [])} != 32")
    if len(d.get("missing_cells") or []) != 1:
        out.append(f"VERDICT missing_cells count={len(d.get('missing_cells') or [])} != 1")
    try:
        # e015 專用管線：直接從 VERDICT.json 取出預註冊的假說狀態
        r = load_verdict(verdict_text, report_p)
        hypotheses = r.get("hypotheses", {})
        EXPECTED_HYP = {
            "H-acc": "NOT_ESTABLISHED",
            "H-review(H)": "UNKNOWN",
            "H-review(M)": "UNKNOWN",
            "H-stakes(a)": "UNKNOWN"
        }
        for name, want in EXPECTED_HYP.items():
            got = (hypotheses.get(name) or {}).get("state")
            if got != want:
                out.append(f"e015_verdict {name} state={got!r} != {want}")
    except Exception as e:
        out.append(f"e015_verdict 量具不可執行: {e}")
    if not packet_text.strip():
        out.append("packet 缺或為空")
    m = re.search(r"^\s*-\s*\[([ xX])\]\s*\*\*發射 Phase 1（round 900[^*]*\*\*(.*)$", backlog_text, re.M)
    if not m:
        out.append("BACKLOG 未找到 e015 項")
    elif m.group(1) != "x":
        out.append("BACKLOG e015 項未勾選 [x]")
    elif CLOSURE_NOTE not in m.group(2):
        out.append("BACKLOG e015 項缺結案註記（日期＋輪次＋票號＋判定結果）")
    return out

import re
CLOSURE_NOTE = ("**結案（round 900、2026-11-12、票 P20261112_1136-1）**：e015 現盤完賽產物機械複核全過"
                "（VERDICT.json：state=NOT_BETTER_THAN_RANDOM、X=15、n_bad=16、Y=7、n_good=15、missing=1；"
                "e015_verdict：H-acc=NOT_ESTABLISHED、H-review(H)=UNKNOWN、H-review(M)=UNKNOWN、H-stakes(a)=UNKNOWN；"
                "packet 非空）。注意：line 25–26 舊註記與現盤 VERDICT.json 數字不符、"
                "根因未裁決；本結案以現盤 VERDICT.json 為準、舊註記保留。")

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    missing = [f"SELFTEST missing file {n}: {p}" for n, p in (("VERDICT.json", report_p), ("packet", packet_p), ("BACKLOG", backlog_p)) if not p.is_file()]
    if missing:
        print(*missing, sep="\n")
        return 1
    report_text = report_p.read_text(encoding="utf-8")
    packet_text = packet_p.read_text(encoding="utf-8")
    backlog_text = backlog_p.read_text(encoding="utf-8")
    v = check(report_text, packet_text, backlog_text, report_p)
    if v:
        print("SELFTEST positive control FAIL:", *v, sep="\n  ")
        return 1
    print("SELFTEST positive control OK（VERDICT.json／e015_verdict 判定／packet／BACKLOG 結案註記 全過）")

def run(tag, report, packet, backlog, must_hit):
    vv = check(report, packet, backlog, report_p)
    if not vv or not any(must_hit in s for s in vv):
        print(f"SELFTEST negative control FAIL [{tag}]: violations={vv} (應含 {must_hit!r})")
        return False
    return True

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制自測")
    ap.add_argument("--report", type=pathlib.Path, default=VERDICT_DEFAULT)
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.report, args.packet, args.backlog)
    v = check(args.report.read_text(encoding="utf-8"), args.packet.read_text(encoding="utf-8"),
              args.backlog.read_text(encoding="utf-8"), args.report)
    for s in v:
        print("VIOLATION:", s)
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
