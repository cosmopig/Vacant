#!/usr/bin/env python3
"""步驟 1：同一批 1,747 個有填行跑 V2（欄位對齊兩題 Noul）與 V3（Choice 選段＋程式比對），以及機制對照（對的行換欄問 V1／V2）。
規則＝ops/redo/audit/judge_v2v3_20261128/PLAN.md（呼叫前已提交）。事後探索性。
金鑰只從環境變數 GEMINI_API_KEY 讀；請求／回應原文寫私有目錄；公開輸出只有 HMAC 行鍵與機率；逐筆記帳（provider＝gemini）。
用法：judge_v2v3.py R1 R2 --private DIR --out DIR [--limit N] [--max-usd 8]"""
from __future__ import annotations
import argparse, concurrent.futures as cf, hashlib, hmac, json, pathlib, re, sys, threading, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import judge_pages as P  # noqa: E402
from judge_pages import M, SRC  # noqa: E402
from judge_gemini_decision import context as v1_context, QUESTION as V1_Q  # noqa: E402

PRICE = 0.10 / 1e6
LEDGER = pathlib.Path.home() / "dev/ops/ctl/api_credit_ledger.jsonl"
KEY = (pathlib.Path.home() / ".config/vacant/audit_hmac.key").read_text().strip().encode()
lk = lambda sid, rep, cid: hmac.new(KEY, f"{sid}|r{rep}|{cid}".encode(), hashlib.sha256).hexdigest()[:20]
Q1 = "Does the value_location row or passage describe the requested field (field and field_scope) for the requested entity, rather than a different field, a different period or a different entity?"
Q2 = "Does the value_location give exactly claimed_value for that field?"
V3_Q = "Which passage gives the requested entity's value for the requested field, as specified by field and field_scope? Choose 'none' if no passage does."


def label_keys(label):
    return [w for w in re.findall(r"[\wÀ-ɏ'’.()–-]+", label) if len(w) >= 4]


def strip_bar(s):
    return s.replace(" | ", " ").replace(" || ", " ")


def table_header(tb):
    for r in tb:
        if r and all(t == "th" for t, _ in r):
            return " | ".join(x for _, x in r)
    return ""


def value_location(pages, val):
    for _, h in pages:
        tbs = P.parse_tables(h)
        locs = P.row_locs(tbs, val)
        if locs:
            i, j, _ = locs[0]
            return f"[table header] {table_header(tbs[i])}\n[row] " + " | ".join(x for _, x in tbs[i][j])
    for _, h in pages:
        pl = SRC._plain(h); ss = P.sentences(pl); s = P.in_sentence(pl, val)
        if s:
            k = ss.index(s) if s in ss else 0
            return "[passage] " + " ".join(ss[max(0, k - 1):k + 2])
    return None


def v3_candidates(pages, val, label):
    keys = [k.lower() for k in label_keys(label)]
    withv, withk = [], []
    seen = set()
    for _, h in pages:
        tbs = P.parse_tables(h)
        vlocs = {(i, j) for i, j, _ in P.row_locs(tbs, val)}
        for i, tb in enumerate(tbs):
            hdr = table_header(tb)
            for j, r in enumerate(tb):
                txt = " | ".join(x for _, x in r)
                seg = (f"{hdr} || {txt}" if hdr else txt)[:500]
                if not txt.strip() or seg in seen:
                    continue
                low = txt.lower(); hits = sum(k in low for k in keys)
                if (i, j) in vlocs:
                    seen.add(seg); withv.append(seg)
                elif hits:
                    seen.add(seg); withk.append((hits, seg))
        for s in P.sentences(SRC._plain(h)):
            if len(s) > 600 or s in seen:
                continue
            low = s.lower(); hits = sum(k in low for k in keys)
            if SRC.plain_contains(s, val):
                seen.add(s); withv.append(s)
            elif hits >= 2:
                seen.add(s); withk.append((hits, s))
    withk.sort(key=lambda x: -x[0])
    return (withv + [s for _, s in withk])[:254]


def seg_has_value(seg, val):
    s = strip_bar(seg)
    return SRC.plain_contains(s, val) or (P.norm(val) and P.norm(val) in P.norm(s))


class Runner:
    def __init__(self, priv, max_usd):
        from google import genai
        self.client = genai.Client(http_options={"api_version": "v1beta"})
        self.lock = threading.Lock(); self.spent = 0.0; self.max_usd = max_usd
        self.resf = open(priv / "v2v3_responses.jsonl", "a"); self.led = open(LEDGER, "a")

    def call(self, tag, key, inp, questions):
        with self.lock:
            if self.spent >= self.max_usd:
                return None, "budget"
        resp = err = None
        for att in range(5):
            try:
                resp = self.client.decisions.create(model="gemini-decision-1", input=inp, questions=questions).model_dump(); break
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {str(e)[:300]}"; time.sleep(3 * (att + 1))
        toks = (resp or {}).get("usage", {}).get("total_input_tokens") or 0
        with self.lock:
            self.spent += toks * PRICE
            self.resf.write(json.dumps({"tag": tag, "key": key, "input": inp, "questions": questions, "response": resp, "error": err}, ensure_ascii=False) + "\n"); self.resf.flush()
            self.led.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "provider": "gemini", "purpose": f"judge_v2v3 {tag}",
                                       "model": "gemini-decision-1", "input_tokens": toks, "output_tokens": 0, "cost_usd": round(toks * PRICE, 8), "cell": key}) + "\n"); self.led.flush()
        return resp, err


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs=2); ap.add_argument("--private", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int); ap.add_argument("--max-usd", type=float, default=8.0); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(); priv = pathlib.Path(a.private); priv.mkdir(parents=True, exist_ok=True); out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    roots = [pathlib.Path(r) for r in a.roots]
    plan = json.loads((roots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    done = {}
    pf = out / "v2v3_lines.jsonl"
    if pf.is_file():
        for l in pf.read_text().splitlines():
            try:
                j = json.loads(l)
            except ValueError:
                continue
            if j.get("score") is not None or j.get("not_on_page") or j.get("n_options") == 0:
                done[(j["tag"], j["key"])] = j
    jobs = []; pages_cache = {}
    for root in roots:
        for c0 in sorted(root.glob("cells/*/r[1-5]/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            claims = sorted(truth[sid]["claims"], key=lambda c: c["id"]); ans0 = truth[sid]["truth"][0]
            vals = M.SD.parse_report((c0 / "report.md").read_text(errors="replace"), truth[sid]["claims"])
            for idx, c in enumerate(claims):
                raw = vals.get(c["id"])
                if raw in (None, "") or not str(raw).strip():
                    continue
                correct = M.strict_status(raw, c["id"], truth[sid]["truth"], 0) == "correct"
                base = {"c0": c0, "key": lk(sid, rep, c["id"]), "domain": "companies" if sid.startswith("cc") else "football",
                        "entity": c.get("entity", ""), "label": c.get("label", ""), "scope": c.get("template_line", ""), "value": raw}
                jobs.append(("V2", base)); jobs.append(("V3", base))
                if correct:
                    for d in range(1, len(claims)):
                        o = claims[(idx + d) % len(claims)]
                        if M.canon_strict(ans0.get(o["id"])) != M.canon_strict(ans0.get(c["id"])):
                            sw = dict(base, label=o.get("label", ""), scope=o.get("template_line", ""))
                            jobs.append(("MECH_V1", sw)); jobs.append(("MECH_V2", sw)); break
    if a.limit:
        jobs = jobs[: a.limit]
    jobs = [j for j in jobs if (j[0], j[1]["key"]) not in done]
    print("jobs", len(jobs), flush=True)
    R = Runner(priv, a.max_usd); outf = open(pf, "a"); wlock = threading.Lock()

    def pages_for(c0):
        k = str(c0)
        if k not in pages_cache:
            pages_cache[k] = P.fetched_pages(c0)
        return pages_cache[k]

    def work(job):
        tag, b = job; pages = pages_for(b["c0"]); val = b["value"]; rec = {"tag": tag, "key": b["key"], "domain": b["domain"]}
        field = f"{b['entity']} — {b['label']}"
        if tag in ("V2", "MECH_V2"):
            loc = value_location(pages, val)
            if loc is None:
                rec.update(score=0.0, not_on_page=True, error=None)
            else:
                ctx = v1_context([SRC._plain(h) for _, h in pages], b["entity"], b["label"])
                inp = json.dumps({"page_text": ctx, "entity": b["entity"], "field": field, "field_scope": b["scope"], "value_location": loc, "claimed_value": val}, ensure_ascii=False)
                resp, err = R.call(tag, b["key"], inp, {"q1": {"type": "noul", "instructions": Q1}, "q2": {"type": "noul", "instructions": Q2}})
                if resp:
                    p1 = resp["answers"]["q1"]["noul"]; p2 = resp["answers"]["q2"]["noul"]
                    rec.update(score=p1 * p2, p_q1=p1, p_q2=p2, not_on_page=False, tokens=resp["usage"]["total_input_tokens"], error=None)
                else:
                    rec.update(score=None, error=err)
        elif tag == "MECH_V1":
            ctx = v1_context([SRC._plain(h) for _, h in pages], b["entity"], b["label"])
            inp = json.dumps({"page_text": ctx, "field": field, "claimed_value": val}, ensure_ascii=False)
            resp, err = R.call(tag, b["key"], inp, {"supported": {"type": "noul", "instructions": V1_Q}})
            rec.update(score=resp["answers"]["supported"]["noul"] if resp else None, tokens=(resp or {}).get("usage", {}).get("total_input_tokens"), error=None if resp else err)
        else:  # V3
            cands = v3_candidates(pages, val, b["label"])
            if not cands:
                rec.update(score=0.0, n_options=0, error=None)
            else:
                crit = {f"o{i+1}": s for i, s in enumerate(cands)}; crit["none"] = "None of the passages gives this field's value."
                inp = json.dumps({"entity": b["entity"], "field": field, "field_scope": b["scope"]}, ensure_ascii=False)
                resp, err = R.call(tag, b["key"], inp, {"seg": {"type": "choice", "instructions": V3_Q, "criteria": crit}})
                if resp:
                    ans = resp["answers"]["seg"]; ch = ans["choice"]; pr = ans.get("confidence") or 0.0
                    has = ch != "none" and seg_has_value(crit[ch], val)
                    rec.update(score=pr * (1.0 if has else 0.0), choice_none=ch == "none", choice_has_value=has, p_choice=pr,
                               n_options=len(cands), tokens=resp["usage"]["total_input_tokens"], error=None)
                else:
                    rec.update(score=None, error=err)
        with wlock:
            outf.write(json.dumps(rec) + "\n"); outf.flush()
        return rec

    n = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for rec in ex.map(work, jobs):
            n += 1
            if n % 200 == 0:
                print(f"{n}/{len(jobs)} spent ${R.spent:.3f}", flush=True)
    print(json.dumps({"jobs_done": n, "spent_usd": round(R.spent, 4)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
