#!/usr/bin/env python3
"""事後探索性先導（2026-11-28，非預註冊）：判別式決策模型（Gemini Decisions，gemini-decision-1）當逐行判定。

每一行＝確認批次 150 份初稿裡的一個有填行。送出：該格 agent 實際抓過的頁面純文字（出口 200 的頁，依 sha 從凍結站取）＋欄位標籤＋初稿寫的值；
問是非題（noul）「這段頁面文字是否支持這個值？」取回機率。不送答案鍵、不送任何路徑或網址。
頁面太長時的固定規則：純文字合計超過 MAXC 字元，就每頁只留「實體名或欄位標籤中長度 ≥4 的詞」每次出現前後 WIN 字元的片段（合併重疊），
合計仍超過 MAXC 就截到 MAXC。
金鑰只從環境變數 GEMINI_API_KEY 讀。請求與回應原文寫到私有目錄（--private）；公開輸出只有 HMAC 行鍵與機率。逐筆記帳到
~/dev/ops/ctl/api_credit_ledger.jsonl（provider＝gemini；$0.10／百萬輸入 token，輸出免費）。
用法：judge_gemini_decision.py --roots R1 R2 --private DIR --out DIR (--sample 60 | --all)
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, sys, time
REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from audit_key import audit_hmac  # noqa: E402
from ops.d2 import expT_metrics as M  # noqa: E402
from vacant_network.trace import sources as SRC  # noqa: E402

MAXC, WIN = 60000, 1200
PRICE_PER_TOK = 0.10 / 1e6
LEDGER = pathlib.Path.home() / "dev/ops/ctl/api_credit_ledger.jsonl"
QUESTION = "Does the page text support the claim? Answer yes only if the page text states this exact value for this field."


def line_key(sid, rep, cid):
    return audit_hmac(f"{sid}|r{rep}|{cid}")


def pages_text(c0: pathlib.Path) -> list[str]:
    shas = set()
    for ej in (c0 / "snapshot" / "vh").glob("trace/projects/*/egress.jsonl"):
        for l in ej.read_text(errors="replace").splitlines():
            try:
                e = json.loads(l)
            except ValueError:
                continue
            if e.get("method") == "GET" and e.get("status") == 200 and e.get("sha256"):
                shas.add(e["sha256"])
    out = []
    for f in sorted((c0 / "site_frozen").glob("*")):
        if f.is_file() and f.name != "index.html" and hashlib.sha256(f.read_bytes()).hexdigest() in shas:
            out.append(SRC._plain(f.read_text(errors="replace")))
    return out


def context(pages: list[str], entity: str, label: str) -> str:
    full = "\n\n".join(pages)
    if len(full) <= MAXC:
        return full
    keys = [entity] + [w for w in re.findall(r"[\wÀ-ɏ'’.-]+", label) if len(w) >= 4]
    keys = [k for k in keys if k]
    pieces = []
    for p in pages:
        spans = []
        low = p.lower()
        for k in keys:
            for m in re.finditer(re.escape(k.lower()), low):
                spans.append((max(0, m.start() - WIN), min(len(p), m.end() + WIN)))
        spans.sort(); merged = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        pieces += [p[a:b] for a, b in merged]
    return "\n...\n".join(pieces)[:MAXC]


def build_lines(roots):
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    lines = []
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"])
            fb = json.loads((c0 / "flags_v2.json").read_text()).get("flags_by_claim") or {}
            pg = None
            for c in truth[sid]["claims"]:
                raw = vals.get(c["id"])
                if raw in (None, "") or not str(raw).strip():      # 分母＝有填行（值非空）；canon_strict 解析不出的值也算有填（2026-11-28 統一分母）
                    continue
                if pg is None:
                    pg = pages_text(c0)
                lines.append({"key": line_key(sid, rep, c["id"]), "set": sid, "rep": rep, "claim": c["id"],
                              "domain": "companies" if sid.startswith("cc") else "football",
                              "entity": c.get("entity", ""), "label": c.get("label", ""), "value": raw,
                              "wrong": M.strict_status(raw, c["id"], truth[sid]["truth"], 0) != "correct",
                              "record_flag": bool((fb.get(c["id"]) or {}).get("flagged")), "_pages": pg})
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--roots", nargs=2, required=True); ap.add_argument("--private", required=True)
    ap.add_argument("--out", required=True); g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sample", type=int); g.add_argument("--all", action="store_true"); ap.add_argument("--max-usd", type=float, default=15.0)
    a = ap.parse_args()
    from google import genai
    client = genai.Client(http_options={"api_version": "v1beta"})
    roots = [pathlib.Path(r) for r in a.roots]; priv = pathlib.Path(a.private); priv.mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    lines = build_lines(roots)
    if a.sample:
        per = a.sample // 2; chosen = []
        for dom in ("football", "companies"):
            ls = sorted([l for l in lines if l["domain"] == dom], key=lambda l: hashlib.sha256(f"{l['key']}:judge-pilot".encode()).hexdigest())
            chosen += ls[:per]
        lines = chosen
    done = {}
    resf = priv / "responses.jsonl"
    if resf.is_file():
        for l in resf.read_text().splitlines():
            j = json.loads(l); done[j["key"]] = j
    spent = 0.0; t_all = []
    with open(resf, "a") as rf, open(LEDGER, "a") as led:
        for i, l in enumerate(lines):
            if l["key"] in done:
                continue
            if spent >= a.max_usd:
                print("max-usd reached"); break
            ctx = context(l["_pages"], l["entity"], l["label"])
            inp = json.dumps({"page_text": ctx, "field": f"{l['entity']} — {l['label']}", "claimed_value": l["value"]}, ensure_ascii=False)
            t0 = time.time(); err = None; resp = None
            for attempt in range(4):
                try:
                    resp = client.decisions.create(model="gemini-decision-1", input=inp,
                                                   questions={"supported": {"type": "noul", "instructions": QUESTION}}).model_dump()
                    break
                except Exception as e:  # noqa: BLE001
                    err = f"{type(e).__name__}: {str(e)[:300]}"; time.sleep(2 * (attempt + 1))
            dt = time.time() - t0; t_all.append(dt)
            toks = (resp or {}).get("usage", {}).get("total_input_tokens") or 0; cost = toks * PRICE_PER_TOK; spent += cost
            p = (resp or {}).get("answers", {}).get("supported", {}).get("noul")
            rec = {"key": l["key"], "p_supported": p, "input_tokens": toks, "latency_s": round(dt, 3), "error": None if resp else err,
                   "ctx_chars": len(ctx), "request_input": inp, "response": resp}
            rf.write(json.dumps(rec, ensure_ascii=False) + "\n"); rf.flush(); done[l["key"]] = rec
            led.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "provider": "gemini", "purpose": "judge_gemini_decision pilot",
                                  "model": "gemini-decision-1", "input_tokens": toks, "output_tokens": 0, "cost_usd": round(cost, 8), "cell": l["key"]}) + "\n"); led.flush()
            if i % 50 == 0:
                print(f"{i}/{len(lines)} spent ${spent:.4f}", flush=True)
    pub = []
    for l in lines:
        d = done.get(l["key"])
        if d:
            pub.append({"key": l["key"], "domain": l["domain"], "p_supported": d["p_supported"], "record_flag": l["record_flag"],
                        "wrong": l["wrong"], "input_tokens": d["input_tokens"], "latency_s": d["latency_s"], "error": bool(d.get("error"))})
    (out / ("judge_lines_sample.jsonl" if a.sample else "judge_lines_all.jsonl")).write_text("".join(json.dumps(x) + "\n" for x in pub))
    toks = [x["input_tokens"] for x in pub]; lat = [x["latency_s"] for x in pub]
    summ = {"lines": len(pub), "errors": sum(x["error"] for x in pub), "mean_input_tokens": round(sum(toks) / max(1, len(toks))),
            "usd_per_line": round(sum(toks) / max(1, len(toks)) * PRICE_PER_TOK, 6), "mean_latency_s": round(sum(lat) / max(1, len(lat)), 3),
            "total_filled_lines": len(build_lines(roots)) if a.sample else len(lines)}
    summ["full_estimate_usd"] = round(summ["usd_per_line"] * summ["total_filled_lines"], 3)
    print(json.dumps(summ, ensure_ascii=False))
    (out / ("pilot_summary.json" if a.sample else "run_summary.json")).write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
