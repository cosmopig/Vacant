"""V1：IFEval（可程式判定的指令）——確定性級聯 vs 直接丟一個 LLM 守門員。

真值（GT）＝**官方 IFEval strict 檢查器**（`data/ifeval_lib/`，google-research，sha256 見
`data/SHA256SUMS`）。受驗的輸出＝官方附的 GPT-4 回應 541 筆。

⚠ 誠實：確定性層用的是**我們自己寫的通用檢查**（`vacant_network/genverify.py`），
不是官方檢查器——所以「確定性層對 GT 的一致率」不是同義反覆，量的是
「一套小的通用檢查詞彙，照規格編譯，能多準地重現一個權威判定」。
官方沒有的型別（語言偵測、句數、重複 prompt……）**刻意不編譯**，留給評審（殘差）。

策略（PLAN.md §V1 發射前寫死）：
  J    ：評審看 prompt＋回應＋全部要求，逐條 PASS/FAIL/UNSURE（每筆 1 通）
  D    ：只跑確定性層，編譯不到的要求 ⇒ unknown（0 token）
  C    ：D ＋ 只把編譯不到的要求交給評審（確定性已 reject ⇒ 不問，0 token）
  C-ns ：同 C 但不短路（逐條準確度用）
重跑：
  NLTK_DATA=<含 punkt、punkt_tab> <有 absl-py langdetect nltk immutabledict 的 python> \
      ops/research_20260924/verifier/exp_ifeval.py gt          # 算官方真值（不花 token）
  python3 ops/research_20260924/verifier/exp_ifeval.py run [--model M] [--limit N]
  python3 ops/research_20260924/verifier/exp_ifeval.py report
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import random
import re
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
DATA = HERE / "data"
RES = HERE / "results"
SEED = 20260924

from vacant_network import genverify as gv  # noqa: E402
from vacant_network.genverify import ACCEPTED, REJECTED, UNKNOWN, Criterion, Spec  # noqa: E402


def load():
    inp = {json.loads(l)["prompt"]: json.loads(l) for l in open(DATA / "input_data.jsonl")}
    rsp = [json.loads(l) for l in open(DATA / "input_response_data_gpt4_20231107_145030.jsonl")]
    items = []
    for i, r in enumerate(rsp):
        # ⚠ 1 筆回應對應的 prompt 在資料集後來被改過（「at least one placeholder」→「3 placeholders」），
        #   input_data.jsonl 裡找不到原 prompt ⇒ 排除，n＝540（PLAN.md §V1 記載）。
        if r["prompt"] not in inp:
            continue
        d = inp[r["prompt"]]
        items.append({"idx": i, "key": d["key"], "prompt": d["prompt"], "response": r["response"],
                      "ids": d["instruction_id_list"],
                      "kwargs": [{k: v for k, v in kw.items() if v is not None} for kw in d["kwargs"]]})
    return items


# ───────────── 官方真值（另一個 venv 跑） ─────────────

def cmd_gt():
    pkg = types.ModuleType("instruction_following_eval")
    pkg.__path__ = [str(DATA / "ifeval_lib")]
    sys.modules["instruction_following_eval"] = pkg
    from instruction_following_eval import instructions_registry as reg
    out = []
    for it in load():
        strict, loose, desc = [], [], []
        for iid, kw in zip(it["ids"], it["kwargs"]):
            cls = reg.INSTRUCTION_DICT[iid]
            ins = cls(iid)
            desc.append(ins.build_description(**kw))
            args = ins.get_instruction_args()
            if args and "prompt" in args:
                ins.build_description(prompt=it["prompt"])
            resp = it["response"]
            strict.append(bool(resp.strip() and ins.check_following(resp)))
            # loose：官方的變體（去掉首行／末行／星號）任一過就算過
            r = resp.split("\n")
            cands = [resp, resp.replace("*", ""), "\n".join(r[1:]).strip(), "\n".join(r[:-1]).strip(),
                     "\n".join(r[1:-1]).strip()]
            cands += [c.replace("*", "") for c in cands[2:]]
            loose.append(any(c.strip() and ins.check_following(c) for c in cands))
        out.append({"idx": it["idx"], "strict": strict, "loose": loose, "desc": desc})
    (RES / "ifeval_gt.json").write_text(json.dumps(out, ensure_ascii=False))
    print("gt", len(out), "prompt-level strict pass", sum(all(o["strict"]) for o in out))


# ───────────── 編譯器：IFEval 規格 → genverify 準則 ─────────────

def compile_criterion(k: int, iid: str, kw: dict) -> Criterion | None:
    cid = f"{k}:{iid}"
    C = lambda check, **p: Criterion(cid, "check", check, p)  # noqa: E731
    if iid == "punctuation:no_comma":
        return C("regex_count", pattern=",", relation="exactly", n=0)
    if iid == "length_constraints:number_words":
        return C("word_count", relation=kw["relation"], n=kw["num_words"])
    if iid == "keywords:forbidden_words":
        return C("forbids", keywords=kw["forbidden_words"])
    if iid == "detectable_format:number_highlighted_sections":
        return C("regex_count", pattern=r"\*[^\n\*]+\*", relation="at least", n=kw["num_highlights"])
    if iid == "keywords:frequency":
        return C("keyword_freq", keyword=kw["keyword"], relation=kw["relation"], n=kw["frequency"])
    if iid == "startend:quotation":
        return C("starts_ends", quoted=True)
    if iid == "change_case:english_lowercase":
        return C("case", case="lower")
    if iid == "change_case:english_capital":
        return C("case", case="upper")
    if iid == "keywords:existence":
        return C("contains_all", keywords=kw["keywords"])
    if iid == "detectable_format:title":
        return C("regex_count", pattern=r"<<[^\n]+>>", relation="at least", n=1)
    if iid == "keywords:letter_frequency":
        return C("letter_freq", letter=kw["letter"], relation=kw["let_relation"], n=kw["let_frequency"])
    if iid == "detectable_format:number_bullet_lists":
        return C("regex_count", pattern=r"^\s*[\*\-]\s", relation="exactly", n=kw["num_bullets"])
    if iid == "detectable_content:number_placeholders":
        return C("regex_count", pattern=r"\[[^\]]*\]", relation="at least", n=kw["num_placeholders"])
    if iid == "length_constraints:number_paragraphs":
        return C("paragraphs", n=kw["num_paragraphs"])
    if iid == "startend:end_checker":
        return C("starts_ends", ends_with=kw["end_phrase"])
    if iid == "detectable_content:postscript":
        return C("regex_count", pattern=r"\s*" + re.escape(kw["postscript_marker"]),
                 relation="at least", n=1, ignore_case=True)
    if iid == "detectable_format:json_format":
        return C("json_parses")
    if iid == "change_case:capital_word_frequency":
        return C("regex_count", pattern=r"\b[A-Z]+\b", relation=kw["capital_relation"],
                 n=kw["capital_frequency"])
    if iid == "detectable_format:multiple_sections":
        return C("regex_count", pattern=r"^\s*" + re.escape(kw["section_spliter"]) + r"\s?\d+",
                 relation="at least", n=kw["num_sections"])
    return None  # 語言、句數、重複 prompt、兩個回答、第 n 段首字、限定回答：留給評審


# ───────────── 評審 ─────────────

SYS = ("You check whether a RESPONSE satisfies each numbered REQUIREMENT. Judge only what is "
       "written. For each requirement answer PASS, FAIL, or UNSURE. Reply with JSON only: "
       '{"results":[{"id":<n>,"verdict":"PASS|FAIL|UNSURE"}]}')


def judge_prompt(it, reqs):
    lines = [f"{n}. {d}" for n, d in reqs]
    return (f"ORIGINAL PROMPT:\n{it['prompt']}\n\nREQUIREMENTS:\n" + "\n".join(lines)
            + f"\n\nRESPONSE:\n<<<\n{it['response']}\n>>>")


def ask_judge(J, it, reqs, tag):
    from judge_claude import parse_json
    rec = J.ask(SYS, judge_prompt(it, reqs), tag)
    out = {}
    d = parse_json(rec.get("text")) if rec and rec.get("ok") else None
    for x in (d or {}).get("results", []) if isinstance(d, dict) else []:
        v = str(x.get("verdict", "")).upper()
        out[int(x.get("id", -1))] = {"PASS": ACCEPTED, "FAIL": REJECTED}.get(v, UNKNOWN)
    return out, rec


def cmd_run(model: str, limit: int | None, workers: int = 6):
    from judge_claude import Judge, overhead_probe
    tag = model.split("-")[1]
    J = Judge(f"ifeval_{tag}", model)
    ov = overhead_probe(J)
    gt = {g["idx"]: g for g in json.loads((RES / "ifeval_gt.json").read_text())}
    items = load()
    if limit:
        items = random.Random(SEED).sample(items, limit)
    rows = []

    def one(it):
        g = gt[it["idx"]]
        crits = [compile_criterion(k, iid, kw) for k, (iid, kw) in enumerate(zip(it["ids"], it["kwargs"]))]
        spec = Spec(it["prompt"], [c for c in crits if c])
        det = gv.evaluate(spec, it["response"], None)
        det_v = {r["id"]: r["verdict"] for r in det["criteria"]}
        per_det = [det_v.get(f"{k}:{iid}", UNKNOWN) if crits[k] else UNKNOWN
                   for k, iid in enumerate(it["ids"])]
        # J：全部要求
        jall, rj = ask_judge(J, it, [(k + 1, d) for k, d in enumerate(g["desc"])], f"J:{it['idx']}")
        per_j = [jall.get(k + 1, UNKNOWN) for k in range(len(it["ids"]))]
        # C-ns：只問編譯不到的
        resid = [(k + 1, g["desc"][k]) for k in range(len(it["ids"])) if crits[k] is None]
        rc = None
        per_c = list(per_det)
        if resid:
            jr, rc = ask_judge(J, it, resid, f"C:{it['idx']}")
            for n, _ in resid:
                per_c[n - 1] = jr.get(n, UNKNOWN)
        short = any(v == REJECTED for v in per_det)
        return {"idx": it["idx"], "ids": it["ids"], "gt_strict": g["strict"], "gt_loose": g["loose"],
                "det": per_det, "judge": per_j, "cascade": per_c,
                "cascade_short_circuited": short and bool(resid),
                "tok_J": (rj or {}).get("tokens_in", 0) + (rj or {}).get("tokens_out", 0),
                "tok_C": ((rc or {}).get("tokens_in", 0) + (rc or {}).get("tokens_out", 0)) if resid else 0,
                "cost_J": (rj or {}).get("cost_usd"), "cost_C": (rc or {}).get("cost_usd") if resid else 0,
                "J_ok": bool(rj and rj.get("ok")), "C_ok": (bool(rc and rc.get("ok")) if resid else None),
                "n_resid": len(resid)}

    with cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, items):
            rows.append(r)
    (RES / f"ifeval_rows_{tag}.json").write_text(json.dumps({"overhead": ov, "rows": rows}))
    print("done", len(rows), ov)


# ───────────── 報告 ─────────────

def _prompt_level(per):
    return gv.aggregate(per)


def metrics(rows, key, gtkey="gt_strict", tokkey=None, short=False):
    """prompt 層：三值 vs GT（全部過＝accepted）。"""
    n = len(rows)
    acc = rej = unk = fa = fr = correct = 0
    tok = 0
    for r in rows:
        per = r[key]
        v = _prompt_level(per)
        g = all(r[gtkey])
        if key == "cascade" and short and r["cascade_short_circuited"]:
            v = REJECTED  # 短路：確定性已經 reject，評審那一通不必打
        if v == ACCEPTED:
            acc += 1; fa += (not g); correct += g
        elif v == REJECTED:
            rej += 1; fr += g; correct += (not g)
        else:
            unk += 1
        if tokkey:
            tok += 0 if (key == "cascade" and short and r["cascade_short_circuited"]) else r[tokkey]
    return {"n": n, "accepted": acc, "rejected": rej, "unknown": unk,
            "false_accept": fa, "false_reject": fr,
            "false_accept_rate_among_accepted": round(fa / acc, 4) if acc else None,
            "decided_accuracy": round(correct / (acc + rej), 4) if acc + rej else None,
            "coverage": round((acc + rej) / n, 4),
            "accuracy_unknown_as_wrong": round(correct / n, 4),
            "tokens_total": tok, "tokens_per_item": round(tok / n, 1)}


def inst_level(rows, key):
    tot = agree = unk = 0
    by_type = {}
    for r in rows:
        for iid, v, g in zip(r["ids"], r[key], r["gt_strict"]):
            t = by_type.setdefault(iid, [0, 0, 0])
            t[0] += 1
            if v == UNKNOWN:
                unk += 1; t[2] += 1
                continue
            tot += 1
            ok = (v == ACCEPTED) == g
            agree += ok; t[1] += ok
    return {"decided": tot, "agree": agree, "unknown": unk,
            "agreement_on_decided": round(agree / tot, 4) if tot else None,
            "by_type": {k: {"n": v[0], "agree": v[1], "unknown": v[2]} for k, v in sorted(by_type.items())}}


def cmd_report():
    out = {}
    for f in sorted(RES.glob("ifeval_rows_*.json")):
        d = json.loads(f.read_text())
        rows = d["rows"]
        ov = d["overhead"]["fixed_overhead_in"] or 0
        tag = f.stem.split("_")[-1]
        nJ = sum(1 for r in rows if r["J_ok"])
        nC = sum(1 for r in rows if r["n_resid"] and not r["cascade_short_circuited"])
        out[tag] = {
            "overhead_fixed_in_per_call": ov,
            "J_calls_failed": sum(1 for r in rows if not r["J_ok"]),
            "prompt_level": {
                "D_deterministic_only": metrics(rows, "det"),
                "J_judge_only": metrics(rows, "judge", tokkey="tok_J"),
                "C_cascade_short_circuit": metrics(rows, "cascade", tokkey="tok_C", short=True),
                "C_cascade_no_short_circuit": metrics(rows, "cascade", tokkey="tok_C"),
            },
            "net_tokens_per_item": {
                "J": round((sum(r["tok_J"] for r in rows) - ov * nJ) / len(rows), 1),
                "C_short": round((sum(r["tok_C"] for r in rows if not r["cascade_short_circuited"])
                                  - ov * nC) / len(rows), 1)},
            "calls_per_item": {"J": 1.0, "C_short": round(nC / len(rows), 3)},
            "cost_usd_total": {"J": round(sum(r["cost_J"] or 0 for r in rows), 4),
                               "C_short": round(sum((r["cost_C"] or 0) for r in rows
                                                    if not r["cascade_short_circuited"]), 4)},
            "instruction_level": {"D": inst_level(rows, "det"), "J": inst_level(rows, "judge"),
                                  "C": inst_level(rows, "cascade")},
            "gt_strict_vs_loose_disagree_prompts": sum(1 for r in rows if all(r["gt_strict"]) != all(r["gt_loose"])),
        }
    # 配對：同一批題目上比 Haiku 與 Sonnet（Sonnet 只跑了抽樣的 150 題）
    fs = {f.stem.split("_")[-1]: json.loads(f.read_text())["rows"] for f in RES.glob("ifeval_rows_*.json")}
    if "haiku" in fs and "sonnet" in fs:
        ids = {r["idx"] for r in fs["sonnet"]}
        hs = [r for r in fs["haiku"] if r["idx"] in ids]
        out["paired_subset_haiku_on_sonnet_items"] = {
            "n": len(hs), "J_judge_only": metrics(hs, "judge", tokkey="tok_J"),
            "C_cascade_short_circuit": metrics(hs, "cascade", tokkey="tok_C", short=True),
            "D_deterministic_only": metrics(hs, "det")}
    (RES / "v1_ifeval_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for tag, o in out.items():
        if "prompt_level" in o:
            print(tag, json.dumps(o["prompt_level"], indent=1), o["net_tokens_per_item"], o["cost_usd_total"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gt", "run", "report"])
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    {"gt": cmd_gt, "run": lambda: cmd_run(a.model, a.limit), "report": cmd_report}[a.cmd]()
