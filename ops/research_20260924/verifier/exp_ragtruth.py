"""V2：RAGTruth（人工標註的幻覺：問答、摘要、資料→文字）——非程式任務的驗證器。

真值＝RAGTruth 人工標註：回應有任何一個標註片段 ⇒ 有幻覺（**rejected 才對**）；
沒有 ⇒ 忠於來源（accepted 才對）。這是 RAGTruth 的回應層定義（Niu et al. 2024）。

樣本（PLAN.md §V2 發射前寫死，seed 20260924）：
  dev  ＝train split，每個任務型別 50 有幻覺＋50 無 ⇒ 300（**只拿來定確定性門檻，不打評審**）
  test ＝test  split，同樣分層 ⇒ 300
⚠ 分層抽樣把盛行率固定在 50%——「接受者裡有幾成其實有幻覺」這個數字依盛行率而變，
  報告同時給逐型別數字與「依 test split 自然盛行率重新加權」的版本。

策略：
  D   ：確定性（反證：回應裡有來源沒有的數字 ⇒ rejected；幾乎逐字取自來源 ⇒ accepted；其餘 unknown）
  J   ：評審（Haiku 4.5／Sonnet 5）看 task prompt（含來源）＋回應，SUPPORTED／UNSUPPORTED／UNSURE＋引文
  Jq  ：J，但 UNSUPPORTED 必須附一段**逐字存在於回應裡**的引文，否則 unknown（同一通，不多花）
  C   ：D → 殘差才問 J（同一通 J 的結果，配對設計；token 只算殘差那幾通）
  Cq  ：D → 殘差才問 Jq
  預算掃描：每題評審 token 上限（呼叫前用字元數估），超過 ⇒ unknown、0 token。
重跑：
  python3 ops/research_20260924/verifier/exp_ragtruth.py sample
  python3 ops/research_20260924/verifier/exp_ragtruth.py dev
  python3 ops/research_20260924/verifier/exp_ragtruth.py run --model claude-haiku-4-5-20251001
  python3 ops/research_20260924/verifier/exp_ragtruth.py run --model claude-sonnet-5
  python3 ops/research_20260924/verifier/exp_ragtruth.py report
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
DATA = HERE / "data" / "ragtruth"
SAMPLES = HERE / "samples"
RES = HERE / "results"
SEED = 20260924
TYPES = ("QA", "Summary", "Data2txt")
PER_CELL = 50

from vacant_network import genverify as gv  # noqa: E402
from vacant_network.genverify import ACCEPTED, REJECTED, UNKNOWN, Criterion, JudgeResult, Spec  # noqa: E402


def source_text(s: dict) -> str:
    si = s["source_info"]
    if isinstance(si, dict) and "passages" in si:
        return si["passages"]
    return si if isinstance(si, str) else json.dumps(si, ensure_ascii=False)


def cmd_sample():
    S = {json.loads(l)["source_id"]: json.loads(l) for l in open(DATA / "source_info.jsonl")}
    R = [json.loads(l) for l in open(DATA / "response.jsonl")]
    rng = random.Random(SEED)
    SAMPLES.mkdir(exist_ok=True)
    for split, name in (("train", "dev"), ("test", "test")):
        out = []
        for t in TYPES:
            for hal in (True, False):
                pool = [r for r in R if r["split"] == split and S[r["source_id"]]["task_type"] == t
                        and bool(r["labels"]) == hal]
                for r in rng.sample(pool, PER_CELL):
                    s = S[r["source_id"]]
                    out.append({"id": r["id"], "task_type": t, "model": r["model"],
                                "hallucinated": hal, "label_types": [x["label_type"] for x in r["labels"]],
                                "prompt": s["prompt"], "source": source_text(s), "response": r["response"]})
        (SAMPLES / f"ragtruth_{name}.jsonl").write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out))
        print(name, len(out))
    # 自然盛行率（重新加權用）
    prev = {t: sum(1 for r in R if r["split"] == "test" and S[r["source_id"]]["task_type"] == t and r["labels"])
            / sum(1 for r in R if r["split"] == "test" and S[r["source_id"]]["task_type"] == t) for t in TYPES}
    (SAMPLES / "ragtruth_test_prevalence.json").write_text(json.dumps(prev, indent=1))
    print(prev)


def load(name):
    return [json.loads(l) for l in open(SAMPLES / f"ragtruth_{name}.jsonl")]


# ───────────── 確定性層（門檻由 dev 決定） ─────────────

IGNORE_SMALL = (0, 10, 31)
RATIOS = (0.8, 0.85, 0.9, 0.95, 1.0)
MIN_PRECISION = 0.9


def det_parts(it, ignore_small, min_ratio):
    spec = Spec(it["prompt"], [], sources={"src": it["source"]})
    vn, _ = gv.chk_numbers_supported(it["response"], {"ignore_small": ignore_small}, spec)
    ve, _ = (gv.chk_extractive(it["response"], {"min_ratio": min_ratio}, spec)
             if min_ratio is not None else (UNKNOWN, ""))
    return vn, ve


def cmd_dev():
    """每個任務型別分開定：反證層的 ignore_small、逐字層的 min_ratio。
    判準寫死：dev 上 precision ≥ 0.9 才啟用（reject 的 precision＝真的有幻覺；
    accept 的 precision＝真的沒有），且至少 5 次觸發；否則該層在該型別停用。"""
    dev = load("dev")
    cfg = {}
    for t in TYPES:
        items = [x for x in dev if x["task_type"] == t]
        best_n = None
        for ig in IGNORE_SMALL:
            rej = [x for x in items if det_parts(x, ig, None)[0] == REJECTED]
            prec = sum(x["hallucinated"] for x in rej) / len(rej) if rej else None
            row = {"ignore_small": ig, "fires": len(rej), "precision": prec}
            cfg.setdefault(t, {}).setdefault("numbers_grid", []).append(row)
            if prec is not None and prec >= MIN_PRECISION and len(rej) >= 5:
                if best_n is None or len(rej) > best_n["fires"]:
                    best_n = row
        best_e = None
        for mr in RATIOS:
            acc = [x for x in items if det_parts(x, 10, mr)[1] == ACCEPTED]
            prec = sum(not x["hallucinated"] for x in acc) / len(acc) if acc else None
            row = {"min_ratio": mr, "fires": len(acc), "precision": prec}
            cfg[t].setdefault("extractive_grid", []).append(row)
            if prec is not None and prec >= MIN_PRECISION and len(acc) >= 5 and best_e is None:
                best_e = row
        cfg[t]["numbers"] = best_n
        cfg[t]["extractive"] = best_e
    (RES / "ragtruth_dev_thresholds.json").write_text(json.dumps(cfg, indent=1))
    print(json.dumps({t: {"numbers": c["numbers"], "extractive": c["extractive"]} for t, c in cfg.items()},
                     indent=1))


# ───────────── 評審 ─────────────

SYS = ("You check whether a RESPONSE is fully supported by the source material contained in the "
       "TASK. A response is UNSUPPORTED if it states anything that contradicts the source or that the "
       "source does not contain. Reply with JSON only: "
       '{"verdict":"SUPPORTED|UNSUPPORTED|UNSURE","quote":"<if UNSUPPORTED, copy the exact unsupported '
       'words from the RESPONSE; else empty>"}')


def judge_prompt(it):
    return f"TASK (includes the source):\n{it['prompt']}\n\nRESPONSE:\n<<<\n{it['response']}\n>>>"


def spec_for(it, cfg, *, det: bool, judge: bool) -> Spec:
    crits = []
    c = cfg[it["task_type"]]
    if det and c["numbers"]:
        crits.append(Criterion("nums", "check", "numbers_supported",
                               {"ignore_small": c["numbers"]["ignore_small"]}, screen=True))
    q = "Is every statement in the response supported by the source?"
    if det and c["extractive"]:
        crits.append(Criterion("faithful", "check", "extractive", {"min_ratio": c["extractive"]["min_ratio"]},
                               question=q, fallback_judge=judge))
    elif judge:
        crits.append(Criterion("faithful", "judge", question=q))
    elif det:
        # 只有反證層：沒有反證也給不出 accepted ⇒ 放一條永遠 unknown 的佔位（不問評審）
        crits.append(Criterion("faithful", "check", "extractive", {"min_ratio": 1.01}))
    return Spec(it["prompt"], crits, sources={"src": it["source"]})


def make_judge_fn(J, it):
    from judge_claude import parse_json

    def fn(spec, output, crits):
        rec = J.ask(SYS, judge_prompt(it), f"rt:{it['id']}")
        d = parse_json(rec.get("text")) if rec and rec.get("ok") else None
        v = str((d or {}).get("verdict", "")).upper()
        verdict = {"SUPPORTED": ACCEPTED, "UNSUPPORTED": REJECTED}.get(v, UNKNOWN)
        jr = JudgeResult(verdict, (rec or {}).get("tokens_in", 0) + (rec or {}).get("tokens_out", 0),
                         quote=(d or {}).get("quote") or None, raw=(rec or {}).get("text"),
                         cost_usd=(rec or {}).get("cost_usd"))
        fn.last = jr
        return {c.id: jr for c in crits}
    fn.last = None
    return fn


def quote_check(verdict, jr, it):
    """Jq：rejected 要附逐字存在於回應裡的引文，否則 unknown。accepted 不動（沒有可核的引文）。"""
    if verdict == REJECTED and not (jr and jr.quote and gv.quote_in(jr.quote, it["response"])):
        return UNKNOWN
    return verdict


def cmd_run(model, workers=6):
    from judge_claude import Judge, overhead_probe
    tag = model.split("-")[1]
    J = Judge(f"ragtruth_{tag}", model)
    ov = overhead_probe(J)
    cfg = json.loads((RES / "ragtruth_dev_thresholds.json").read_text())
    test = load("test")

    def one(it):
        fnJ = make_judge_fn(J, it)
        rJ = gv.evaluate(spec_for(it, cfg, det=False, judge=True), it["response"], fnJ)
        jr = fnJ.last
        fnC = make_judge_fn(J, it)
        rC = gv.evaluate(spec_for(it, cfg, det=True, judge=True), it["response"], fnC)
        rD = gv.evaluate(spec_for(it, cfg, det=True, judge=False), it["response"], None)
        vJq = quote_check(rJ["verdict"], jr, it)
        # Cq：只有在 C 真的問了評審時，評審那一票才受引文檢查
        vCq = rC["verdict"]
        if rC["judge_calls"]:
            vCq = quote_check(rC["verdict"], fnC.last, it) if rC["verdict"] != REJECTED or all(
                r["verdict"] != REJECTED for r in rC["criteria"] if r["layer"] == "check") else rC["verdict"]
        return {"id": it["id"], "task_type": it["task_type"], "hallucinated": it["hallucinated"],
                "D": rD["verdict"], "J": rJ["verdict"], "Jq": vJq, "C": rC["verdict"], "Cq": vCq,
                "tok_J": rJ["judge_tokens"], "tok_C": rC["judge_tokens"], "calls_C": rC["judge_calls"],
                "cost_J": rJ["judge_cost_usd"], "cost_C": rC["judge_cost_usd"],
                "est_tokens": gv.estimate_tokens(judge_prompt(it) + SYS),
                "judge_raw": (jr.raw if jr else None), "judge_quote": (jr.quote if jr else None),
                "D_criteria": rD["criteria"]}

    with cf.ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(one, test))
    (RES / f"ragtruth_rows_{tag}.json").write_text(json.dumps({"overhead": ov, "rows": rows},
                                                              ensure_ascii=False))
    print("done", len(rows), ov)


# ───────────── 報告 ─────────────

def score(rows, key, prev=None, tok=None, caps=None):
    def cell(rs):
        a = [r for r in rs if r[key] == ACCEPTED]
        j = [r for r in rs if r[key] == REJECTED]
        u = [r for r in rs if r[key] == UNKNOWN]
        fa = sum(r["hallucinated"] for r in a)
        fr = sum(not r["hallucinated"] for r in j)
        return {"n": len(rs), "accepted": len(a), "rejected": len(j), "unknown": len(u),
                "false_accept": fa, "false_reject": fr,
                "false_accept_rate_among_accepted": round(fa / len(a), 4) if a else None,
                "precision_of_reject": round(1 - fr / len(j), 4) if j else None,
                "decided_accuracy": round((len(a) - fa + len(j) - fr) / (len(a) + len(j)), 4) if a or j else None,
                "coverage": round((len(a) + len(j)) / len(rs), 4),
                "tokens_per_item": round(sum(r[tok] for r in rs) / len(rs), 1) if tok else 0}
    out = {"all": cell(rows)}
    for t in TYPES:
        out[t] = cell([r for r in rows if r["task_type"] == t])
    if prev:
        # 依自然盛行率重新加權「接受者中的幻覺比例」：P(hal|acc) = p·P(acc|hal) / (p·P(acc|hal)+(1-p)·P(acc|ok))
        rw = {}
        for t in TYPES:
            rs = [r for r in rows if r["task_type"] == t]
            h = [r for r in rs if r["hallucinated"]]
            o = [r for r in rs if not r["hallucinated"]]
            pa_h = sum(r[key] == ACCEPTED for r in h) / len(h)
            pa_o = sum(r[key] == ACCEPTED for r in o) / len(o)
            p = prev[t]
            den = p * pa_h + (1 - p) * pa_o
            rw[t] = {"prevalence": round(p, 4),
                     "false_accept_rate_among_accepted_reweighted": round(p * pa_h / den, 4) if den else None}
        out["reweighted_to_test_prevalence"] = rw
    return out


def budget_curve(rows, jkey, caps, ov):
    """呼叫前上限：est_tokens > cap ⇒ 不問（unknown、0 token）。C 系列只對真的問了評審的那些題套上限。"""
    pts = []
    for cap in caps:
        acc = rej = unk = fa = fr = 0
        tok = 0
        for r in rows:
            asked = r["calls_C"] > 0 if jkey.startswith("C") else True
            v = r[jkey]
            if asked and cap is not None and r["est_tokens"] > cap:
                v = r["D"] if jkey.startswith("C") else UNKNOWN
            elif asked:
                tok += r["tok_C"] if jkey.startswith("C") else r["tok_J"]
            if v == ACCEPTED:
                acc += 1; fa += r["hallucinated"]
            elif v == REJECTED:
                rej += 1; fr += not r["hallucinated"]
            else:
                unk += 1
        n = len(rows)
        pts.append({"cap": cap, "tokens_per_item": round(tok / n, 1),
                    "coverage": round((acc + rej) / n, 4),
                    "decided_accuracy": round((acc - fa + rej - fr) / (acc + rej), 4) if acc + rej else None,
                    "accuracy_unknown_as_wrong": round((acc - fa + rej - fr) / n, 4),
                    "false_accept_rate_among_accepted": round(fa / acc, 4) if acc else None})
    return pts


def cmd_report():
    prev = json.loads((SAMPLES / "ragtruth_test_prevalence.json").read_text())
    out = {}
    for f in sorted(RES.glob("ragtruth_rows_*.json")):
        d = json.loads(f.read_text())
        rows, ov = d["rows"], d["overhead"]["fixed_overhead_in"] or 0
        tag = f.stem.split("_")[-1]
        nC = sum(r["calls_C"] for r in rows)
        caps = [0, 250, 500, 750, 1000, 1500, 2000, 3000, None]
        out[tag] = {
            "overhead_fixed_in_per_call": ov,
            "D": score(rows, "D", prev), "J": score(rows, "J", prev, "tok_J"),
            "Jq": score(rows, "Jq", prev, "tok_J"), "C": score(rows, "C", prev, "tok_C"),
            "Cq": score(rows, "Cq", prev, "tok_C"),
            "judge_calls_per_item": {"J": 1.0, "C": round(nC / len(rows), 4)},
            "net_tokens_per_item": {"J": round((sum(r["tok_J"] for r in rows) - ov * len(rows)) / len(rows), 1),
                                    "C": round((sum(r["tok_C"] for r in rows) - ov * nC) / len(rows), 1)},
            "cost_usd_total": {"J": round(sum(r["cost_J"] or 0 for r in rows), 4),
                               "C": round(sum(r["cost_C"] or 0 for r in rows), 4)},
            "budget_curve": {k: budget_curve(rows, k, caps, ov) for k in ("J", "Jq", "C", "Cq")},
            "judge_unparsable": sum(1 for r in rows if r["J"] == UNKNOWN and r["judge_raw"] and "UNSURE" not in (r["judge_raw"] or "")),
        }
    (RES / "v2_ragtruth_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for tag, o in out.items():
        print(tag, {k: o[k]["all"] for k in ("D", "J", "Jq", "C", "Cq")}, o["net_tokens_per_item"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "dev", "run", "report"])
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    a = ap.parse_args()
    {"sample": cmd_sample, "dev": cmd_dev, "run": lambda: cmd_run(a.model),
     "report": cmd_report}[a.cmd]()
