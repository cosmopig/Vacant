#!/usr/bin/env python3
"""實驗 T 的稽核包匯出（給只能讀公開 repo 的獨立複核）。

輸出（out_dir）：
- `expT_cells.csv`／`.json`：逐格（組、重複、臂、主機、輪數、停止原因、退回／送回行數、c0 與最終的正確行數／已填行數／總行數、
  傷害三類、token、牆鐘、Haiku 呼叫與花費、作廢、時間、鏈驗證）。評分用 `ops/d2/expT_metrics.score_cell`（同一份嚴格評分）。
- `expT_lines.jsonl`：逐行的狀態（correct／wrong／missing…、錯誤類型、是否被標、是否送回、傷害旗標）；**不含任何值**——
  教材與答案在私有目錄、不進公開 repo（refs-not-on-github），值只給 sha256。
- `expT_chains/<組>__<重複>__<臂>/feedback_chain.ndjson`＋`.pub.json`＋`expT_chain_anchors.json`（stream_id、鏈頭、公鑰、verify_chain）。
  ⚠ 回饋鏈的 payload 若含回饋文字，裡面可能引用頁面值；本匯出只放鏈的雜湊結構（payload 換成 sha256），驗簽要用私有原檔。
- `expT_haiku.jsonl`：TE／TER 每格的 Haiku 呼叫——模型、prompt／回覆的 sha256、token、花費、牆鐘、送上去的行數；**不放 prompt／回覆本文**。
用法：export_expT_audit.py <root> <out_dir>
"""
from __future__ import annotations
import csv, hashlib, json, pathlib, shutil, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_metrics as M  # noqa: E402
from vacant_network.logbook import LogEntry, Logbook  # noqa: E402
from vacant_network.identity import PublicIdentity  # noqa: E402

def sha(s) -> str:
    return hashlib.sha256((s if isinstance(s, bytes) else str(s).encode())).hexdigest()

def main(root: str, out: str) -> None:
    root, out = pathlib.Path(root), pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    run = json.loads((root / "RUN.json").read_text()); plan = run["plan_body"]
    truth = M.load_manifests_with_truth(plan); reps = int(plan.get("reps") or 2)
    arms = list(plan.get("arms")); rows, lines, anchors, haiku = [], [], [], []
    for sid in truth:
        for rep in range(1, reps + 1):
            rdir = root / "cells" / sid / f"r{rep}"
            c0p = rdir / "c0" / "report.md"; c0 = c0p.read_text(errors="replace") if c0p.is_file() else ""
            for arm in arms:
                adir = rdir / arm; cp = adir / "cell.json"
                if not cp.is_file():
                    continue
                cd = json.loads(cp.read_text())
                base = {"set": sid, "rep": rep, "arm": arm, "host": cd.get("provider"), "ts": cd.get("ts"),
                        "infra_void": bool(cd.get("infra_void"))}
                if cd.get("infra_void"):
                    rows.append({**base, "error": cd.get("error")}); continue
                fp = adir / "report.md"; final = fp.read_text(errors="replace") if fp.is_file() else ""
                ch = adir / "feedback_chain.ndjson"
                r = M.score_cell(cd, c0, final, truth[sid], chain_path=ch if ch.is_file() else None, verify_chain=True)
                ls = r.pop("lines")
                st = lambda key, v: sum(1 for x in ls if x[key] == v)
                filled = lambda key: sum(1 for x in ls if x[key] not in ("missing", None))
                rows.append({**base, "rounds_run": r["rounds_run"], "stop_reason": r["stop_reason"],
                             "c0_flagged": len(cd.get("c0_flagged_ids") or []), "sent_back": r["sent_back_total"],
                             "sent_back_fixed": r["sent_back_fixed"], "withheld": r["withheld_total"],
                             "n_lines": len(ls), "c0_correct": st("before_status", "correct"), "c0_filled": filled("before_status"),
                             "final_correct": st("after_status", "correct"), "final_filled": filled("after_status"),
                             "harm_c2w_or_d": r["harm_c2w_or_d"], "harm_b2w": r["harm_b2w"], "harm_total": r["harm_total"],
                             "tokens_total": r["tokens_total"], "extra_tokens_total": r["extra_tokens_total"], "calls_total": r["calls_total"],
                             "wall_s_total": r["wall_s_total"], "extra_wall_s": r["extra_wall_s"],
                             "haiku_called": r["haiku_called"], "haiku_tokens_total": r["haiku_tokens_total"], "haiku_cost_usd": r["haiku_cost_usd"],
                             "chain_ok": r["chain_ok"], "final_report_sha256": sha(final), "c0_report_sha256": sha(c0)})
                for x in ls:
                    lines.append({"set": sid, "rep": rep, "arm": arm, "claim_id": x["claim_id"],
                                  **{k: x[k] for k in ("before_status", "after_status", "before_etype", "after_etype", "digit_bucket",
                                                       "c0_flagged", "sent_back", "harm_c2w_or_d", "harm_b2w")},
                                  "before_value_sha256": sha(x["before_value"]) if x["before_value"] is not None else None,
                                  "after_value_sha256": sha(x["after_value"]) if x["after_value"] is not None else None})
                he = cd.get("haiku_escalation")
                if he:
                    haiku.append({"set": sid, "rep": rep, "arm": arm, **{k: he.get(k) for k in (
                        "called", "model", "prompt_sha256", "response_sha256", "input_tokens", "output_tokens",
                        "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd", "wall_s", "stop_reason", "withheld")},
                        "escalated_lines": len(he.get("escalated_claim_ids") or []), "fetched_pages": len(he.get("fetched_page_shas") or [])})
                if ch.is_file():
                    ents = [LogEntry.from_json(json.loads(l)) for l in ch.read_text().splitlines() if l.strip()]
                    pub = json.loads((adir / "feedback_chain.pub.json").read_text()) if (adir / "feedback_chain.pub.json").is_file() else {}
                    ok = Logbook(ents).verify_chain(PublicIdentity.from_hex(pub["vacant_id"], pub["pub_hex"])) if pub else None
                    dst = out / "expT_chains" / f"{sid}__r{rep}__{arm}"; dst.mkdir(parents=True, exist_ok=True)
                    with open(dst / "feedback_chain_hashed.ndjson", "w") as f:
                        for e in ents:
                            d = e.to_json(); d["payload_sha256"] = sha(json.dumps(d.pop("payload"), sort_keys=True, ensure_ascii=False)); d["entry_hash"] = e.hash()
                            f.write(json.dumps(d) + "\n")
                    if pub: shutil.copyfile(adir / "feedback_chain.pub.json", dst / "feedback_chain.pub.json")
                    anchors.append({"set": sid, "rep": rep, "arm": arm, "events": len(ents), "chain_sha256": sha(ch.read_bytes()),
                                    "stream_id": Logbook(ents).stream_id(), "head": Logbook(ents).head(),
                                    "pub_hex": pub.get("pub_hex"), "verify_chain": ok})
    (out / "expT_cells.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(out / "expT_cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    with open(out / "expT_lines.jsonl", "w") as f:
        for x in lines: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with open(out / "expT_haiku.jsonl", "w") as f:
        for x in haiku: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    (out / "expT_chain_anchors.json").write_text(json.dumps(anchors, indent=1))
    blob = "".join(p.read_text() for p in out.rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl", ".csv", ".ndjson"))
    for bad in ("/home/", "d2_private", "100.119.", "100.86."):
        assert bad not in blob, f"private string leaked: {bad}"
    print("cells", len(rows), "void", sum(r["infra_void"] for r in rows), "lines", len(lines), "haiku", len(haiku),
          "chains", len(anchors), "verify_ok", sum(1 for a in anchors if a["verify_chain"]))

if __name__ == "__main__":
    main(*sys.argv[1:3])
