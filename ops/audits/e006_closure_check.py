#!/usr/bin/env python3
"""e006 OpenCode polyglot 170 格評測結案機械複核（2026-11-12、票 P20261112_1326-1）。
2026-11-11 人類常設定案第 2.b 條：一小片一張票、驗收綁可機械複核的量。完賽產物：
REPORT.json（cells_scored=170、infra=7、五臂 n/pass/rate、A_vs_C/H/M/S mcnemar_p
0.4531/0.2891/1.0/0.7266）＋e006_verdict 判定（H-acc/H-review(H)/H-stakes(a)=NOT_ESTABLISHED、
H-review(M)=UNKNOWN；成本 2×A 紅線 H/M 超、C/S 未超）＋packet 非空＋BACKLOG 第 85 行
結案記錄（目標行 sha256 釘住、改動即紅）。對齊 e016/e004 架構；唯讀；0 model calls。
CI-home 兼容：缺省路徑皆絕對系統路徑或 repo 相對（REPO 自 __file__）、不依賴 Path.home()。"""
import argparse
import hashlib
import importlib.util
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
REPORT_DEFAULT = pathlib.Path("/srv/vlab/runs/e006_opencode_polyglot/REPORT.json")
PACKET_DEFAULT = REPO / "ops/vlab/packets/e006_opencode_polyglot.md"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
VERDICT_TOOL = REPO / "ops/vlab/tools/e006_verdict.py"
PER_ARM = {"A": (34, 14, 0.4118), "C": (34, 17, 0.5), "H": (34, 10, 0.2941), "M": (34, 15, 0.4412), "S": (34, 12, 0.3529)}
PAIRED_P = {"A_vs_C": 0.4531, "A_vs_H": 0.2891, "A_vs_M": 1.0, "A_vs_S": 0.7266}
EXPECT_STATE = {"H-acc": "NOT_ESTABLISHED", "H-review(H)": "NOT_ESTABLISHED", "H-review(M)": "UNKNOWN", "H-stakes(a)": "NOT_ESTABLISHED"}
COST_OVER = {"C": False, "H": True, "M": True, "S": False}
BACKLOG_KEY = "e006 完賽收尾"
BACKLOG_VERDICT_NOTE = "e006_verdict.py 判定"
BACKLOG_LINE_SHA256 = "7a8c22fa240761578f08b08ef09117cc44a2b28bfde4c977b50603bff92e3494"


def load_verdict(report_text: str, report_p: pathlib.Path) -> dict:
    """跑 e006_verdict 量具（同 e004/e016 的 importlib 接法）；AUDIT.json 與 REPORT 同目錄存在時才載入。"""
    spec = importlib.util.spec_from_file_location("e006_verdict", VERDICT_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    audit_p = report_p.parent / "AUDIT.json"
    audit = json.loads(audit_p.read_text(encoding="utf-8")) if audit_p.is_file() else None
    return mod.evaluate_hypotheses(json.loads(report_text), audit)


def check(report_text: str, packet_text: str, backlog_text: str, report_p: pathlib.Path = REPORT_DEFAULT) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(report_text)
    except json.JSONDecodeError:
        return ["REPORT.json 無法解析為 JSON"]
    if d.get("cells_scored") != 170:
        out.append(f"REPORT cells_scored={d.get('cells_scored')!r} != 170")
    if len(d.get("infra") or []) != 7:
        out.append(f"REPORT infra 數={len(d.get('infra') or [])} != 7")
    for arm, want in PER_ARM.items():
        a = (d.get("per_arm") or {}).get(arm) or {}
        if (a.get("n"), a.get("pass"), a.get("rate")) != want:
            out.append(f"REPORT per_arm[{arm}] n/pass/rate={a.get('n')!r}/{a.get('pass')!r}/{a.get('rate')!r} != {want[0]}/{want[1]}/{want[2]}")
    for pair, want in PAIRED_P.items():
        p = ((d.get("paired") or {}).get(pair)) or {}
        if p.get("mcnemar_p_two_sided") != want:
            out.append(f"REPORT {pair} mcnemar_p_two_sided={p.get('mcnemar_p_two_sided')!r} != {want}")
    try:
        r = load_verdict(report_text, report_p)
        for name, want in EXPECT_STATE.items():
            if (r["hypotheses"].get(name) or {}).get("state") != want:
                out.append(f"e006_verdict {name} state != {want}")
        for arm, want in COST_OVER.items():
            if (r["cost_redline_2xA"]["arms"].get(arm) or {}).get("over_2x_A_cost") != want:
                out.append(f"e006_verdict 成本 2×A 紅線 {arm} over != {want}")
    except Exception as e:
        out.append(f"e006_verdict 量具不可執行: {e}")
    if not packet_text.strip():
        out.append("packet 缺或為空")
    found = next((l for l in backlog_text.splitlines() if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
    else:
        if not found.lstrip().startswith("- [x]"):
            out.append(f"BACKLOG e006 項未勾選 [x]: {found.lstrip()[:60]}")
        if BACKLOG_VERDICT_NOTE not in found:
            out.append(f"BACKLOG e006 項缺裁決註記: {found.lstrip()[:60]}")
        if hashlib.sha256(found.encode("utf-8")).hexdigest() != BACKLOG_LINE_SHA256:
            out.append(f"BACKLOG e006 目標行 sha256 漂移（第 85 行釘住 {BACKLOG_LINE_SHA256[:12]}…、改動即紅）")
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
    v = check(report, packet, backlog, report_p)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:", *v, sep="\n  ")
        return 1
    print("SELFTEST 正控制 OK（REPORT.json／e006_verdict 判定／packet／BACKLOG 第 85 行結案記錄 全過）")

    def run(tag, rr, pp, bb, must_hit) -> bool:  # 負控制須命中指定違規字串才算生效
        vv = check(rr, pp, bb, report_p)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True

    ok = True  # 負控制（票面要求）：篡改 pass 數、篡改 McNemar p、取消勾選、刪裁決註記 必紅
    ok &= run("n1 REPORT pass 數篡改", report.replace('"pass": 14', '"pass": 15', 1), packet, backlog, "per_arm[A]")
    ok &= run("n2 REPORT McNemar p 篡改", report.replace('"mcnemar_p_two_sided": 0.4531', '"mcnemar_p_two_sided": 0.01', 1), packet, backlog, "A_vs_C")
    ok &= run("n3 BACKLOG 取消勾選", report, packet, backlog.replace("- [x] **e006 完賽收尾", "- [ ] **e006 完賽收尾", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG 裁決註記刪除", report, packet, backlog.replace(BACKLOG_VERDICT_NOTE, "", 1), "缺裁決註記")
    if not ok:
        return 1
    print("VERDICT: E006_CLOSURE_OK")
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
    v = check(report, packet, backlog, args.report)
    for s in v:
        print("VIOLATION:", s)
    return 1 if v else 0

if __name__ == "__main__":
    raise SystemExit(main())
