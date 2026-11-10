"""LLM arms that test the two prompt changes from the offline diagnosis.

FORCED_NONE        question only, forced A/B + p_A (no 'unsure' option).
FORCED_PRECEDENT5  + this person's own decisions on 5 OTHER priced products
                   (Vacant's accept/reject feedback loop, simulated with wave-4
                   items that are not the target). Non-pricing items get no
                   precedents. Same forced A/B + p_A output.

Online-feedback protocol: precedents are the same person's answers on other
wave-4 items, never the target item. This is a different protocol from the
frozen wave 1-3 -> wave 4 split and is labelled as such in every output.
Data and predictions are written only under ~/.cache/vacant (outside the repo).

  BASE=... TOK=... python llm_forced.py --sample /workspace/vacant-twin2k-10 \
      --arms FORCED_NONE FORCED_PRECEDENT5 --out ~/.cache/vacant/llm_forced_10
"""
import argparse, json, os, pickle, random, re, time, urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache/vacant/twin2k500"
PROMPT = (
    "Predict which option this specific person chose. You must pick A or B.\n"
    "Reply with one JSON object and no other text:\n"
    '{{"prediction":"A|B","p_A":0.0-1.0}}\n'
    "p_A is your probability that the person chose A. Use about 0.5 when you have little to go on,\n"
    "but still pick the more likely option.\n\n"
    "{precedents}"
    "Question:\n{question}\n"
)

def precedent_block(w4, target, k, seed):
    pricing = [q for q in w4 if q.startswith("QID9_") and q != target]
    if not target.startswith("QID9_") or k == 0:
        return ""
    rng = random.Random(f"{seed}:{target}")
    rng.shuffle(pricing)
    lines = []
    for q in pricing[:k]:
        lab, stem, opts, _ = w4[q]
        m = re.search(r"following product in that category: (.*?)\. The product is priced at: (\$[0-9,.]+)", stem)
        choice = opts[0] if lab == "option_1" else opts[1]
        lines.append(f"- {m.group(1)} at {m.group(2).rstrip('.')}: {'bought' if choice.startswith('Yes') else 'did not buy'}")
    return "This person's own recent decisions on other products (accept/reject history):\n" + "\n".join(lines) + "\n\n"

def ask(base, tok, model, prompt, timeout=120):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0, "max_tokens": 60, "reasoning_effort": "none"}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except Exception:
        d = {}
    pred = d.get("prediction") if d.get("prediction") in ("A", "B") else None
    try:
        pa = float(d.get("p_A"))
    except Exception:
        pa = None
    return pred, pa

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True)
    ap.add_argument("--arms", nargs="+", default=["FORCED_NONE", "FORCED_PRECEDENT5"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=os.environ.get("VACANT_MODEL", "qwen3.8:27b"))
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    D = pickle.load(open(CACHE / "compact.pkl", "rb"))
    pids = json.load(open(Path(a.sample) / "manifest.json"))["pids"]
    out = Path(a.out).expanduser(); out.mkdir(parents=True, exist_ok=True)
    pred_path = out / "predictions.jsonl"
    done = set()
    if pred_path.exists():
        for line in pred_path.read_text().splitlines():
            r = json.loads(line); done.add((r["pid"], r["arm"], r["qid"]))
    fh = pred_path.open("a")
    for arm in a.arms:
        k = 5 if arm == "FORCED_PRECEDENT5" else 0
        for pid in pids:
            w4 = D[pid]["w4"]
            for qid, (lab, stem, opts, fam) in w4.items():
                if (pid, arm, qid) in done:
                    continue
                order = random.Random(f"{a.seed}:{pid}:{qid}").randrange(2)  # same A/B order rule as twin2k._presentation
                A, B = (opts[0], opts[1]) if order == 0 else (opts[1], opts[0])
                truth = "A" if (lab == "option_1") == (order == 0) else "B"
                prompt = PROMPT.format(precedents=precedent_block(w4, qid, k, a.seed), question=f"{stem}\nA. {A}\nB. {B}")
                if a.dry_run:
                    print(prompt); return
                t0 = time.time(); text = err = None
                for _ in range(2):
                    try:
                        text = ask(os.environ["BASE"], os.environ["TOK"], a.model, prompt); break
                    except Exception as e:
                        err = repr(e)
                pred, pa = parse(text)
                fh.write(json.dumps({"protocol": "online-feedback" if k else "forced-choice", "pid": pid, "arm": arm, "qid": qid,
                                     "prediction": pred, "p_A": pa, "truth": truth, "raw": text, "error": None if text else err,
                                     "latency_s": round(time.time() - t0, 2)}) + "\n"); fh.flush()
    fh.close()

if __name__ == "__main__":
    main()
