"""V3：要求交付物**附上逐字引文**之後，確定性層能做多少、評審能省多少（PLAN.md §V3）。

流程：
  1. 從 RAGTruth test split 的 Summary、Data2txt 來源各抽 30 個（seed 20260924）。
  2. Haiku 4.5 照來源原本的任務寫，**格式規定**：每一句後面附 `[[quote: 來源原文]]`。
  3. 每份產出做兩個版本：原樣（真值：沒有注入錯誤）＋注入一個錯誤（真值：有錯）。
     注入是確定性程式，三種各三分之一：數字（改值）、專有名詞（換成來源沒有的名字）、
     否定（在 is/was/are/were/has/have 後面加 not）。**引文不動**。
     ⚠ 合成真值：「原樣」＝沒有注入錯誤，**不等於**經過查證的忠實；只能講「對這三種注入」。
  4. 策略：
       Jfull ：評審看整份任務（含來源）＋產出（同 V2 的評審）
       E     ：確定性——每句都有引文、引文逐字在來源、句中數字都在來源、
               句中專有名詞都在來源；任一不成立 ⇒ rejected；全過 ⇒ unknown（沒有反證 ≠ 有根據）
       Jclaim：評審只看（句子, 引文）配對，逐句 SUPPORTED/UNSUPPORTED/UNSURE
       EJ    ：E → 殘差才問 Jclaim
重跑：python3 ops/research_20260924/verifier/exp_evidence.py gen|run|report
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
DATA = HERE / "data" / "ragtruth"
RES = HERE / "results"
SEED = 20260924
MODEL = "claude-haiku-4-5-20251001"

from vacant_network import genverify as gv  # noqa: E402
from vacant_network.genverify import ACCEPTED, REJECTED, UNKNOWN  # noqa: E402
from exp_ragtruth import SYS as SYS_FULL, source_text  # noqa: E402

GEN_SYS = ("You write the requested text. Format rule: after EVERY sentence, add evidence copied "
           "word-for-word from the source, like this: Sentence one. [[quote: exact words from the "
           "source]] Sentence two. [[quote: exact words from the source]] Do not add anything else.")
CLAIM_SYS = ("For each numbered CLAIM, decide whether its EVIDENCE supports it. A claim is UNSUPPORTED "
             "if it states anything the evidence does not say or contradicts. Reply with JSON only: "
             '{"results":[{"id":<n>,"verdict":"SUPPORTED|UNSUPPORTED|UNSURE"}]}')
PAIR = re.compile(r"(.*?)\[\[quote:\s*(.*?)\]\]", re.S)
FAKE_NAMES = ["Hartwell", "Brisbane", "Okonkwo", "Valdoria", "Marlowe", "Kessington"]


def pairs_of(text: str) -> list[tuple[str, str]]:
    return [(s.strip(), q.strip()) for s, q in PAIR.findall(text) if s.strip()]


def cmd_gen():
    from judge_claude import Judge
    S = [json.loads(l) for l in open(DATA / "source_info.jsonl")]
    R = [json.loads(l) for l in open(DATA / "response.jsonl")]
    test_src = {r["source_id"] for r in R if r["split"] == "test"}
    rng = random.Random(SEED)
    picks = []
    for t in ("Summary", "Data2txt"):
        pool = sorted((s for s in S if s["task_type"] == t and s["source_id"] in test_src),
                      key=lambda s: s["source_id"])
        picks += rng.sample(pool, 30)
    J = Judge("evidence_gen", MODEL)

    def one(s):
        rec = J.ask(GEN_SYS, s["prompt"], f"gen:{s['source_id']}")
        return {"source_id": s["source_id"], "task_type": s["task_type"], "prompt": s["prompt"],
                "source": source_text(s), "output": rec.get("text") if rec else None,
                "gen_tokens": (rec or {}).get("tokens_in", 0) + (rec or {}).get("tokens_out", 0)}
    with cf.ThreadPoolExecutor(6) as ex:
        outs = list(ex.map(one, picks))
    (RES / "evidence_gen.json").write_text(json.dumps(outs, ensure_ascii=False))
    print("gen", len(outs), "with pairs", sum(1 for o in outs if o["output"] and pairs_of(o["output"])))


# ───────────── 注入 ─────────────

def inject(pairs, source, rng):
    kinds = ["number", "entity", "negation"]
    rng.shuffle(kinds)
    for kind in kinds:
        idx = list(range(len(pairs)))
        rng.shuffle(idx)
        for i in idx:
            s, q = pairs[i]
            if kind == "number":
                m = list(re.finditer(r"\b\d+(?:\.\d+)?\b", s))
                if m:
                    x = rng.choice(m)
                    v = x.group(0)
                    nv = str(int(float(v)) + rng.choice([2, 3, 7, 11])) if "." not in v else f"{float(v) + 0.5:g}"
                    s2 = s[:x.start()] + nv + s[x.end():]
                    return i, kind, s2
            elif kind == "entity":
                caps = [m for m in re.finditer(r"(?<=\s)[A-Z][a-z]{3,}\b", s)]
                if caps:
                    x = rng.choice(caps)
                    name = next(n for n in FAKE_NAMES if n.lower() not in source.lower())
                    return i, kind, s[:x.start()] + name + s[x.end():]
            else:
                m = re.search(r"\b(is|was|are|were|has|have)\b(?! not)", s)
                if m:
                    return i, kind, s[:m.end()] + " not" + s[m.end():]
    return None


def render(pairs):
    return " ".join(f"{s} [[quote: {q}]]" for s, q in pairs)


# ───────────── 確定性 E ─────────────

def det_E(pairs, source, raw_output) -> tuple[str, str]:
    if not pairs:
        return REJECTED, "no [[quote:]] pairs (format not met)"
    leftover = PAIR.sub("", raw_output).strip()
    if len(leftover) > 40:
        return REJECTED, "text outside sentence+quote pairs"
    for n, (s, q) in enumerate(pairs, 1):
        if not gv.quote_in(q, source):
            return REJECTED, f"claim {n}: quote not found verbatim in source"
    src_nums = gv.numbers_in(source)
    for n, (s, q) in enumerate(pairs, 1):
        miss = [x for x in gv.numbers_in(s) if x not in src_nums]
        if miss:
            return REJECTED, f"claim {n}: numbers not in source {miss}"
        for m in re.finditer(r"(?<=\s)[A-Z][a-z]{3,}\b", s):
            if m.group(0).lower() not in source.lower():
                return REJECTED, f"claim {n}: name '{m.group(0)}' not in source"
    return UNKNOWN, "no counter-evidence (not evidence of support)"


def claim_prompt(pairs):
    return "\n\n".join(f"CLAIM {n}: {s}\nEVIDENCE {n}: {q}" for n, (s, q) in enumerate(pairs, 1))


def cmd_run():
    from judge_claude import Judge, parse_json, overhead_probe
    J = Judge("evidence_judge", MODEL)
    ov = overhead_probe(J)
    gen = json.loads((RES / "evidence_gen.json").read_text())
    rng = random.Random(SEED)
    items = []
    for g in gen:
        pairs = pairs_of(g["output"] or "")
        items.append({**g, "variant": "clean", "has_error": False, "pairs": pairs,
                      "text": g["output"] or "", "inject": None})
        inj = inject(pairs, g["source"], rng) if pairs else None
        if inj:
            i, kind, s2 = inj
            p2 = list(pairs)
            p2[i] = (s2, pairs[i][1])
            items.append({**g, "variant": "injected", "has_error": True, "pairs": p2,
                          "text": render(p2), "inject": {"claim": i + 1, "kind": kind}})

    def one(it):
        from exp_ragtruth import judge_prompt
        full = J.ask(SYS_FULL, judge_prompt({"prompt": it["prompt"], "response": it["text"]}),
                     f"full:{it['source_id']}:{it['variant']}")
        d = parse_json(full.get("text")) if full and full.get("ok") else None
        vfull = {"SUPPORTED": ACCEPTED, "UNSUPPORTED": REJECTED}.get(str((d or {}).get("verdict", "")).upper(), UNKNOWN)
        vE, whyE = det_E(it["pairs"], it["source"], it["text"])
        vclaim, tok_claim = UNKNOWN, 0
        if it["pairs"]:
            cr = J.ask(CLAIM_SYS, claim_prompt(it["pairs"]), f"claim:{it['source_id']}:{it['variant']}")
            dc = parse_json(cr.get("text")) if cr and cr.get("ok") else None
            per = {}
            for x in (dc or {}).get("results", []) if isinstance(dc, dict) else []:
                per[int(x.get("id", -1))] = {"SUPPORTED": ACCEPTED, "UNSUPPORTED": REJECTED}.get(
                    str(x.get("verdict", "")).upper(), UNKNOWN)
            vclaim = gv.aggregate([per.get(n, UNKNOWN) for n in range(1, len(it["pairs"]) + 1)])
            tok_claim = (cr or {}).get("tokens_in", 0) + (cr or {}).get("tokens_out", 0)
        vEJ = REJECTED if vE == REJECTED else vclaim
        return {"source_id": it["source_id"], "task_type": it["task_type"], "variant": it["variant"],
                "has_error": it["has_error"], "inject": it["inject"], "n_claims": len(it["pairs"]),
                "Jfull": vfull, "E": vE, "E_why": whyE, "Jclaim": vclaim, "EJ": vEJ,
                "tok_Jfull": (full or {}).get("tokens_in", 0) + (full or {}).get("tokens_out", 0),
                "tok_Jclaim": tok_claim, "tok_EJ": 0 if vE == REJECTED else tok_claim,
                "calls_EJ": 0 if vE == REJECTED or not it["pairs"] else 1}
    with cf.ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(one, items))
    (RES / "evidence_rows.json").write_text(json.dumps({"overhead": ov, "rows": rows}, ensure_ascii=False))
    print("done", len(rows))


def cmd_report():
    d = json.loads((RES / "evidence_rows.json").read_text())
    rows, ov = d["rows"], d["overhead"]["fixed_overhead_in"] or 0
    gen = json.loads((RES / "evidence_gen.json").read_text())

    def sc(key, tok=None, calls=None, rs=None):
        rs = rs or rows
        a = [r for r in rs if r[key] == ACCEPTED]
        j = [r for r in rs if r[key] == REJECTED]
        fa = sum(r["has_error"] for r in a)
        fr = sum(not r["has_error"] for r in j)
        n = len(rs)
        ncalls = sum(r[calls] for r in rs) if calls else (n if tok else 0)
        return {"n": n, "accepted": len(a), "rejected": len(j), "unknown": n - len(a) - len(j),
                "false_accept": fa, "false_reject": fr,
                "decided_accuracy": round((len(a) - fa + len(j) - fr) / (len(a) + len(j)), 4) if a or j else None,
                "accuracy_unknown_as_wrong": round((len(a) - fa + len(j) - fr) / n, 4),
                "tokens_per_item": round(sum(r[tok] for r in rs) / n, 1) if tok else 0,
                "net_tokens_per_item": round((sum(r[tok] for r in rs) - ov * ncalls) / n, 1) if tok else 0}
    by_kind = {}
    for k in ("number", "entity", "negation"):
        rs = [r for r in rows if r["inject"] and r["inject"]["kind"] == k]
        by_kind[k] = {"n": len(rs), "E_rejects": sum(r["E"] == REJECTED for r in rs),
                      "Jfull_rejects": sum(r["Jfull"] == REJECTED for r in rs),
                      "Jclaim_rejects": sum(r["Jclaim"] == REJECTED for r in rs),
                      "EJ_rejects": sum(r["EJ"] == REJECTED for r in rs)}
    clean = [r for r in rows if not r["has_error"]]
    out = {"overhead_fixed_in_per_call": ov,
           "generated": len(gen), "generated_with_pairs": sum(1 for g in gen if g["output"] and pairs_of(g["output"])),
           "gen_tokens_per_output": round(sum(g["gen_tokens"] for g in gen) / len(gen), 1),
           "Jfull": sc("Jfull", "tok_Jfull"), "E": sc("E"), "Jclaim": sc("Jclaim", "tok_Jclaim"),
           "EJ": sc("EJ", "tok_EJ", "calls_EJ"), "by_injection_kind": by_kind,
           "clean_E_rejects_reasons": sorted({r["E_why"].split(":")[-1].strip()[:60] for r in clean if r["E"] == REJECTED}),
           "clean_E_reject_rate": round(sum(r["E"] == REJECTED for r in clean) / len(clean), 4)}
    (RES / "v3_evidence_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"gen": cmd_gen, "run": cmd_run, "report": cmd_report}[sys.argv[1]]()
