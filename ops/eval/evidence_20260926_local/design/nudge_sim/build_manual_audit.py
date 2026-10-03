"""Attach the evidence line (turn T1, thinking/text) to each manual label in nudge_sim.MANUAL.

Output: manual_audit.json. The labels themselves were set by reading the transcripts; this script
only records, for each label, the first line in turn T1 whose tokens scorer.py accepts, so the
label can be re-checked without re-reading the whole transcript.
"""
import json
import os
import re

from parse_runs import latest_runs, parse_session, expected
from candidates import scorer, normalise_like_testsh, extract, accepted, answer_shaped
from nudge_sim import MANUAL, HERE


def line_hit(line, gold):
    if "," in gold:
        m = re.search(r"`([^`]+)`", line)
        cand = m.group(1) if m else line.split(":", 1)[-1]
        return scorer.question_scorer(normalise_like_testsh(cand).lower(), gold)
    toks = re.findall(r"-?\d[\d,]*\.?\d*|[A-Za-z_][\w\-]*(?: [A-Z][a-z]+)?", line)
    return any(scorer.question_scorer(x.lower(), gold) for x in toks
               if x.lower() not in ("the", "a", "an", "it"))


def main():
    L = latest_runs()
    out = []
    for key, (t1, sw, conf) in sorted(MANUAL.items(), key=lambda x: (x[0][1], int(x[0][2]))):
        turns, _ = parse_session(L[key])
        gold = expected(key[2])
        ev = None
        for src in ("thinking", "text"):  # prefer a cue line (answer/result/...) the extractor accepts
            for line in turns[t1 - 1][src].split("\n"):
                if any(accepted(d["cand"], gold) and answer_shaped(d["cand"], gold) and not d["hedged"]
                       for d in extract(line)):
                    ev = f"t{t1} {src}: {line.strip()[:240]}"
                    break
            if ev:
                break
        for src in ("thinking", "text") if not ev else ():
            for line in turns[t1 - 1][src].split("\n"):
                if line.strip() and line_hit(line, gold):
                    ev = f"t{t1} {src}: {line.strip()[:240]}"
                    break
            if ev:
                break
        sw_ev = None
        if sw:
            for line in turns[sw - 1]["thinking"].split("\n"):
                if re.search(r"\bI (?:will|'ll) (?:use|bet|go)", line):
                    sw_ev = f"t{sw} thinking: {line.strip()[:240]}"
                    break
        L_ = L[key]
        out.append({"model": key[0], "arm": key[1], "task": key[2], "gold": gold, "T1": t1, "switch": sw,
                    "conf": conf, "n_turns": L_["requests"], "evidence": ev, "switch_evidence": sw_ev,
                    "trial": os.path.join(L_["job"], L_["trial"])})
    json.dump(out, open(os.path.join(HERE, "manual_audit.json"), "w"), ensure_ascii=False, indent=1)
    for o in out:
        print(o["model"], o["arm"], o["task"], o["T1"], o["switch"], o["conf"], "|", (o["evidence"] or "NONE")[:150])


if __name__ == "__main__":
    main()
