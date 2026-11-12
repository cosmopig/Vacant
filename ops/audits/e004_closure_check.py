#!/usr/bin/env python3
"""e004 OpenCode 五臂全盤評測（e004_opencode_polyglot）結案機械複核（round 1493、票 P20261112_0723-1）。
2026-11-11 人類常設定案第 2.b 條：一小片一張票、驗收綁可機械複核的量。現盤完賽產物：REPORT.json
（cells_scored=8、infra=13、A 3/4=0.75、C 1/4=0.25、A_vs_C mcnemar_p=0.5）＋e004_verdict 判定
（H-acc=NOT_ESTABLISHED；H-review(H)/H-review(M)/H-stakes(a)=UNKNOWN）＋packet 非空＋
BACKLOG 活檔（~/dev/ops）line 50 結案註記。對齊 e010 架構；唯讀；0 model calls。
CI-home 兼容：缺省路徑皆絕對系統路徑或 repo 相對（REPO 自 __file__）、不依賴 Path.home()。
repo 內 ops/BACKLOG.md 是 e010 釘住（sha256）之凍結快照、本票不碰、結案只記活檔；活檔 line 54
舊註記（round 708：170 格、A 14/34…）與現盤數字不符、根因未裁決、舊註記保留。
"""
import argparse
import importlib.util
import json
import pathlib
import re

REPORT_DEFAULT = pathlib.Path("/srv/vlab/runs/e004_opencode_polyglot/REPORT.json")
REPO = pathlib.Path(__file__).resolve().parents[2]
PACKET_DEFAULT = REPO / "ops/vlab/packets/e004_opencode_polyglot.md"
BACKLOG_DEFAULT = pathlib.Path("/home/user1/dev/ops/BACKLOG.md")
VERDICT_TOOL = REPO / "ops/vlab/tools/e004_verdict.py"
EXPECT_STATE = {"H-acc": "NOT_ESTABLISHED", "H-review(H)": "UNKNOWN", "H-review(M)": "UNKNOWN", "H-stakes(a)": "UNKNOWN"}
CLOSURE_NOTE = ("**結案（round 1493、2026-11-12、票 P20261112_0723-1）**：e004 現盤完賽產物機械複核全過"
                "（REPORT.json：cells_scored=8、infra=13、A 3/4=0.75、C 1/4=0.25、A_vs_C mcnemar_p=0.5；"
                "e004_verdict：H-acc=NOT_ESTABLISHED、H-review(H)=UNKNOWN、H-review(M)=UNKNOWN、H-stakes(a)=UNKNOWN；"
                "packet 非空）。注意：line 54 舊註記（round 708：170 格、A 14/34…）與現盤 REPORT.json 數字不符、"
                "根因未裁決；本結案以現盤 REPORT.json 為準、舊註記保留。")

def load_verdict(report_text: str, report_p: pathlib.Path) -> dict:
    """跑 e004_verdict 量具（同 e010 的 importlib 接法）；AUDIT.json 與 REPORT 同目錄存在時才載入。"""
    spec = importlib.util.spec_from_file_location("e004_verdict", VERDICT_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    audit_p = report_p.parent / "AUDIT.json"
    audit = json.loads(audit_p.read_text(encoding="utf-8")) if audit_p.is_file() else None
    return mod.evaluate_hypotheses(json.loads(report_text), audit)

def check(report_text: str, packet_text: str, backlog_text: str,
          report_p: pathlib.Path = REPORT_DEFAULT) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out = []
    d = json.loads(report_text)
    if d.get("cells_scored") != 8:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r} != 8")
    if len(d.get("infra") or []) != 13:
        out.append(f"REPORT infra 數={len(d.get('infra') or [])} != 13")
    for arm, want in (("A", (4, 3, 0.75)), ("C", (4, 1, 0.25))):
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    pair = ((d.get("paired") or {}).get("A_vs_C")) or {}
    if pair.get("mcnemar_p_two_sided") != 0.5:
        out.append(f"REPORT A_vs_C mcnemar_p_two_sided={pair.get('mcnemar_p_two_sided')!r} != 0.5")
    try:
        r = load_verdict(report_text, report_p)
        for name, want in EXPECT_STATE.items():
            got = (r["hypotheses"].get(name) or {}).get("state")
            if got != want:
                out.append(f"e004_verdict {name} state={got!r} != {want}")
    except Exception as e:
        out.append(f"e004_verdict 量具不可執行: {e}")
    if not packet_text.strip():
        out.append("packet 缺或為空")
    m = re.search(r"^\s*-\s*\[([ xX])\]\s*\*\*e004 OpenCode[^*]*\*\*(.*)$", backlog_text, re.M)
    if not m:
        out.append("BACKLOG 未找到 e004 項")
    elif m.group(1) != "x":
        out.append("BACKLOG e004 項未勾選 [x]")
    elif CLOSURE_NOTE not in m.group(2):
        out.append("BACKLOG e004 項缺結案註記（日期＋輪次＋票號＋判定結果）")
    return out

def selftest(report_p: pathlib.Path, packet_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    missing = [f"SELFTEST missing file {n}: {p}" for n, p in (("REPORT.json", report_p), ("packet", packet_p), ("BACKLOG", backlog_p)) if not p.is_file()]
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
    print("SELFTEST positive control OK（REPORT.json／e004_verdict 判定／packet／BACKLOG 結案註記 全過）")

    def run(tag, report, packet, backlog, must_hit):  # 負控制須命中指定違規字串才算生效
        vv = check(report, packet, backlog, report_p)
        if not vv or not any(must_hit in s for s in vv):
            print(f"SELFTEST negative control FAIL [{tag}]: violations={vv} (應含 {must_hit!r})")
            return False
        return True
    ok = True  # 負控制（票面要求）：篡改 pass 數、篡改 verdict 狀態、取消勾選、刪結案註記 必紅
    ok &= run("n1 REPORT pass 數篡改", report_text.replace('"pass": 3', '"pass": 4', 1), packet_text, backlog_text, "per_arm[A]")
    ok &= run("n2 verdict 狀態篡改", report_text.replace('"mcnemar_p_two_sided": 0.5', '"mcnemar_p_two_sided": 0.01', 1).replace('"C_only": 0', '"C_only": 3', 1),
              packet_text, backlog_text, "H-acc")
    ok &= run("n3 BACKLOG 取消勾選", report_text, packet_text, backlog_text.replace("- [x] **e004", "- [ ] **e004", 1), "未勾選 [x]")
    ok &= run("n4 結案註記刪除", report_text, packet_text, backlog_text.replace(CLOSURE_NOTE, "", 1), "缺結案註記")
    if not ok: return 1
    print("VERDICT: E004_CLOSURE_OK")
    print("  files:", report_p, packet_p, backlog_p, sep="\n  ")
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
    v = check(args.report.read_text(encoding="utf-8"), args.packet.read_text(encoding="utf-8"),
              args.backlog.read_text(encoding="utf-8"), args.report)
    for s in v:
        print("VIOLATION:", s)
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
