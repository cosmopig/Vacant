#!/usr/bin/env python3
"""實驗 T 探索批次：給獨立複核的補充匯出（附錄 B 補充 B21：值雜湊一律加鹽 HMAC-SHA256；鍵只在本機 ~/.config/vacant/audit_hmac.key）。2026-11-28。

輸出（out_dir）：
  expT_truth_hmac.jsonl     每組、每行、每個修訂 k 的真值（canon_strict 後）HMAC。
  expT_lines_hmac.jsonl     每格每行：before／after 值（canon_strict 後）的 HMAC；after_matches_k（k=0..K）、before_matches_k；
                            after_matches_latest（＝最後一個修訂；**不是**直連當下的線上版本，見下）。
  expT_net_calls.jsonl      每次 agent 執行裡每一個含網址的抓取呼叫：指令類別（curl／wget／python／node／其他）、目標主機、
                            網址路徑的 HMAC、是否在執行窗內對到出口紀錄或伺服器紀錄、工具回傳是否像 HTML 頁面（掃回傳，不只參數）。
                            指令原文不輸出（含本機路徑）。
  README.md                 做不到的項目：直連當下線上維基的修訂編號與該修訂的真值——需要另外查維基修訂歷史，本匯出沒有做。
等值比對：同一把鍵下，相同的正規化值得到相同的 HMAC，可以跨檔比對；沒有鍵無法窮舉還原。
用法：export_expT_hmac_supplement.py <root> <out_dir>
"""
from __future__ import annotations
import hashlib, hmac, json, pathlib, re, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_metrics as M  # noqa: E402
import scan_leak as S  # noqa: E402

_KEY = None


def key() -> bytes:
    global _KEY
    if _KEY is None:
        _KEY = (pathlib.Path.home() / ".config/vacant/audit_hmac.key").read_text().strip().encode()
    return _KEY


H = lambda s: None if s is None else hmac.new(key(), s.encode("utf-8"), hashlib.sha256).hexdigest()
FETCH = re.compile(r"\b(curl|wget|requests\.\w+\(|urlopen\(|urllib\.request|fetch\(|http\.get\()[^|;&]*?(https?://([A-Za-z0-9.\-]+)(?::\d+)?([^\s\"'\\|;&)]*))", re.I)


def klass(tok: str) -> str:
    t = tok.lower()
    return "curl" if t == "curl" else "wget" if t == "wget" else "python" if ("requests" in t or "url" in t) else "node_or_js" if "fetch" in t else "other"


def main() -> None:
    root, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    plan = json.loads((root / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    with open(out / "expT_truth_hmac.jsonl", "w") as f:
        for sid, st in truth.items():
            for c in st["claims"]:
                for k, tk in enumerate(st["truth"]):
                    f.write(json.dumps({"set": sid, "claim": c["id"], "k": k, "truth_hmac": H(M.canon_strict(tk.get(c["id"])))}) + "\n")
    reps = int(plan.get("reps") or 2)
    with open(out / "expT_lines_hmac.jsonl", "w") as f:
        for sid, st in truth.items():
            tr = st["truth"]; K = len(tr)
            for rep in range(1, reps + 1):
                rd = root / "cells" / sid / f"r{rep}"
                if not (rd / "c0" / "report.md").is_file():
                    continue
                before = M.SD.parse_report((rd / "c0" / "report.md").read_text(errors="replace"), st["claims"])
                for arm in plan["arms"]:
                    rp = rd / arm / "report.md"
                    if not rp.is_file():
                        continue
                    after = M.SD.parse_report(rp.read_text(errors="replace"), st["claims"])
                    for c in st["claims"]:
                        cid = c["id"]; b = M.canon_strict(before.get(cid)); a = M.canon_strict(after.get(cid))
                        tk = [M.canon_strict(t.get(cid)) for t in tr]
                        f.write(json.dumps({"set": sid, "rep": rep, "arm": arm, "claim": cid,
                                            "before_hmac": H(b), "after_hmac": H(a),
                                            "after_matches_k": [a is not None and a == t for t in tk],
                                            "before_matches_k": [b is not None and b == t for t in tk],
                                            "after_matches_latest": a is not None and a == tk[-1]}) + "\n")
    acc = [json.loads(l) for l in (root / "access.jsonl").read_text().splitlines() if l.strip()]
    with open(out / "expT_net_calls.jsonl", "w") as f:
        for log in sorted((root / "cells").glob("*/r*/*/**/run/agent.log")):
            rel = log.relative_to(root / "cells").parts
            rj = json.loads((log.parent / "run.json").read_text()) if (log.parent / "run.json").is_file() else {}
            t0, t1 = rj.get("t_start"), rj.get("t_end")
            seen = {a.get("host") for a in acc if t0 and t1 and t0 - 1 <= a.get("ts", 0) <= t1 + 1}
            cell = root / "cells" / rel[0] / rel[1]
            arm = rel[2]; rnd = rel[3] if rel[3].startswith("round_") else "c0"
            vhs = [cell / "c0" / "snapshot" / "vh"] if arm == "c0" else [cell / arm / "final" / "vh"]
            eg_hosts = set()
            for vh in vhs:
                for ej in vh.glob("trace/projects/*/egress.jsonl"):
                    for line in ej.read_text(errors="replace").splitlines():
                        try:
                            e = json.loads(line)
                        except ValueError:
                            continue
                        if t0 and t1 and t0 * 1000 - 1000 <= e.get("ts_ms", 0) <= t1 * 1000 + 1000:
                            eg_hosts.add(str(e.get("url", "")).split("://", 1)[-1].split("/", 1)[0].split(":")[0])
            for tn, args, res in S.calls(log):
                for m in FETCH.finditer(args):
                    host = m.group(3).lower(); path = m.group(4) or "/"
                    f.write(json.dumps({"set": rel[0], "rep": int(rel[1][1:]), "arm": arm, "round": rnd, "tool": tn,
                                        "command_class": klass(m.group(1)), "target_host": host, "path_hmac": H(path),
                                        "own_source_host": host == f"{rel[0]}-{rel[1]}.d2-sources.example",
                                        "matched_egress_or_server": host in eg_hosts or host in seen,
                                        "output_looks_like_html": bool(re.search(r"<!doctype html|<html", res, re.I)),
                                        "t_window": [t0, t1]}) + "\n")
    (out / "README.md").write_text("""# 實驗 T 探索批次：HMAC 補充匯出（2026-11-28）
- 值雜湊一律 HMAC-SHA256（鍵只在執行方本機，不進 git）。同一把鍵下等值可比對；沒有鍵無法窮舉還原。
- 正規化：`expT_metrics.canon_strict`（和評分同一口徑）。
- `after_matches_latest` 是「和教材裡最後一個修訂相符」，**不是**直連當下的線上維基版本。
- **沒做到的**：每次直連線上維基當下的修訂編號與該修訂的真值。需要另外查維基的修訂歷史（對外查詢），本匯出沒有做。
- `expT_net_calls.jsonl` 不含指令原文（原文含本機路徑）；`output_looks_like_html` 是掃工具回傳得到的。
""")
    print("done")


if __name__ == "__main__":
    main()
