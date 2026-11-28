#!/usr/bin/env python3
"""回溯掃描（2026-11-28；vacant-hope 要求）：以前「真實頁面」批次的 agent 有沒有直連外網，以及產品 gc 有沒有刪掉出口頁面內容。
只讀已存紀錄、逐檔串流。每個 root 報：agent 執行數；有「直連」的執行數（指令抓的主機在執行窗內來源伺服器沒有任何紀錄；
經代理的外部請求會被伺服器記成 404，所以沒紀錄＝直連）；連到哪些主機；回傳像 HTML 的直連呼叫數；
gc：vh 目錄裡 gc_report.json 有刪檔的格數與刪檔總數；RUN.json 記的產品版本。
用法：retro_net_scan.py <root> [<root> ...] --out OUT.json
"""
import collections, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import scan_leak as S
FETCH = re.compile(r"\b(?:curl|wget|requests\.\w+\(|urlopen\(|urllib\.request|fetch\(|http\.get\()[^|;&]*?https?://([A-Za-z0-9.\-]+)", re.I)

def scan(root: pathlib.Path):
    acc_by_host = collections.defaultdict(list)
    if (root / "access.jsonl").is_file():
        with open(root / "access.jsonl") as f:
            for line in f:
                try:
                    a = json.loads(line)
                except ValueError:
                    continue
                acc_by_host[a.get("host")].append(a.get("ts", 0))
    runs = direct_runs = calls = html = 0; hosts = collections.Counter(); arms = collections.Counter()
    for log in root.glob("cells/**/run/agent.log"):
        runs += 1
        rj = {}
        try:
            rj = json.loads((log.parent / "run.json").read_text())
        except Exception:
            pass
        t0, t1 = rj.get("t_start"), rj.get("t_end")
        had = False
        for tn, args, res in S.calls(log):
            for m in FETCH.finditer(args):
                h = m.group(1).lower()
                if h.endswith(".d2-sources.example") or h in ("127.0.0.1", "localhost") or re.match(r"^[\d.]+$", h):
                    continue
                ts = acc_by_host.get(h, [])
                logged = any((t0 is None or t0 - 1 <= t) and (t1 is None or t <= t1 + 1) for t in ts) if ts else False
                if not logged:
                    calls += 1; hosts[h] += 1; had = True
                    if re.search(r"<!doctype html|<html|mw-parser-output|infobox", res, re.I):
                        html += 1
        if had:
            direct_runs += 1; arms[str(log.relative_to(root / "cells")).split("/")[1]] += 1
    gc_cells = gc_files = 0
    for g in root.glob("cells/**/vh/gc_report.json"):
        try:
            d = json.loads(g.read_text())
        except Exception:
            continue
        n = int(d.get("files_removed") or 0)
        if n:
            gc_cells += 1; gc_files += n
    pv = None
    try:
        pv = json.loads((root / "RUN.json").read_text()).get("plan_body", {}).get("product_version")
    except Exception:
        pass
    return {"root": root.name, "agent_runs": runs, "runs_with_direct_external": direct_runs, "direct_calls": calls,
            "direct_calls_html_like_output": html, "hosts": dict(hosts.most_common(12)), "direct_runs_by_arm": dict(arms),
            "gc_cells_with_removed_files": gc_cells, "gc_files_removed": gc_files, "product_version": pv}

def main():
    args = sys.argv[1:]; out = args[args.index("--out") + 1]; roots = [a for a in args[:args.index("--out")]]
    res = []
    for r in roots:
        p = pathlib.Path(r)
        if (p / "cells").is_dir():
            res.append(scan(p)); print(json.dumps(res[-1], ensure_ascii=False)[:400], flush=True)
    pathlib.Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
