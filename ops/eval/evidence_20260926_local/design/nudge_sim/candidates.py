"""Candidate-final-answer extraction from assistant thinking / visible text (regex, no model).

Two cue tiers:
  strict  = explicit answer language: "answer is/should be/:", "final answer", "I'll go with X",
            "I will write/output/answer/submit X", "write X to answer.txt".
  broad   = strict + result language: "the result is X", "so/thus/therefore ... is X",
            "rounded to N decimals ...: X", "the highest/lowest/most/top ... is X",
            "<noun>: X" for percentage/fraud rate/average/total/count/answer lines.
Each captured span is cleaned (markdown, quotes, trailing sentence) and normalised the way
test.sh does (first line, xargs-like trim) before scoring with the task's scorer.py.
"""
import re
import sys

from parse_runs import PIN

sys.path.insert(0, PIN + "/dabstep-9/tests")
import scorer  # noqa: E402  (identical sha256 across all 79 tasks)

_V = r"(?:is|are|was|should be|would be|will be|must be|becomes|=|:|->|→|equals)"

STRICT = [
    re.compile(r"\b(?:final\s+)?answer\s*(?:\([^)]*\)\s*)?(?:is\s+(?:likely\s+|probably\s+|then\s+|indeed\s+)?|should be\s+|would be\s+|will be\s+|must be\s+|=\s*|:\s*|->\s*)(?P<c>.+)", re.I),
    re.compile(r"\bI(?:'ll| will| would|'d| am going to| should| can| must)\s+(?:just\s+|now\s+|then\s+)?(?:go with|output|answer|submit|report|provide|return|put|write)\s+(?:the (?:final )?answer\s+)?(?:as\s+|with\s+)?(?P<c>.+)", re.I),
    re.compile(r"\b(?:final|my)\s+(?:answer|result|value)\s*(?:is\s+|:\s*|=\s*)(?P<c>.+)", re.I),
    re.compile(r"\b(?:writ(?:e|ing)|sav(?:e|ing)|put(?:ting)?)\s+[`'\"]?(?P<c>[^`'\"\n]{1,200}?)[`'\"]?\s+(?:to|into|in)\s+[`'\"]?(?:/app/)?answer\.txt", re.I),
]
BROAD = STRICT + [
    re.compile(r"\b(?:the\s+)?result\s+(?:is|was|would be|should be|=|:)\s*(?P<c>.+)", re.I),
    re.compile(r"\b(?:so|thus|therefore|hence)\b[,:]?\s+(?:the\s+)?[\w`'\"\- ]{0,60}?\b(?:is|are|=)\s+(?P<c>.+)", re.I),
    re.compile(r"\bround(?:ed|ing)?\b[^\n]{0,40}?(?:decimal|places?|decimals)\b[^\n:=]{0,20}?(?:[:=,]|is|gives|->|→)\s*(?:it(?:'s| is)\s+|this is\s+|that is\s+|we get\s+|i get\s+)?(?P<c>.+)", re.I),
    re.compile(r"\bthe\s+(?:highest|lowest|largest|smallest|most|least|top|best|worst|maximum|minimum|max|min)\b[\w`'\"\- ]{0,60}?\b(?:is|are|was|=)\s+(?P<c>.+)", re.I),
    re.compile(r"^\s*[-*]?\s*(?:\*\*)?(?:percentage|fraud rate|average|mean|total|count|number|value|answer|result)(?:\*\*)?\s*[:=]\s*(?P<c>.+)", re.I),
]


def _clean(c):
    c = c.strip()
    # cut at a sentence end: '. ' / '.$' not between digits; also ' because', ' since', ' (', ' which'
    m = re.search(r"(?<!\d)\.(?=\s|$)|\.(?=\s+[A-Z])|\s+(?:because|since|which|as it|as this|but|and I|and then|so I|, so|, which|, because)\b|\s\(|;\s", c)
    if m:
        c = c[:m.start()]
    c = c.replace("**", "").replace("`", "").replace("$", "")
    c = re.sub(r"\\(?:text|mathbf|boxed)\{([^}]*)\}", r"\1", c)
    c = c.strip().strip("\"'“”‘’").strip()
    c = c.rstrip(".,:;!?").strip().strip("\"'").strip()
    return c


def normalise_like_testsh(s):
    s = s.split("\n")[0]
    s = s.replace('"', "").replace("'", "")
    return " ".join(s.split())


HEDGE = re.compile(r"\b(?:if|whether|could|might|maybe|perhaps|suppose|supposing|assuming|or|wait|unless|what if)\b", re.I)


def extract(text, tier="broad"):
    """Return list of dicts {tier, cand, hedged} in order of appearance.

    hedged = the line, before the cue, contains if/whether/could/might/maybe/or/wait/...,
    or the line ends with '?', or the candidate starts with 'not'/contains ' or '/'?'."""
    pats = STRICT if tier == "strict" else BROAD
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        hits = []
        for rx in pats:
            for m in rx.finditer(line):
                c = _clean(m.group("c"))
                if not c or len(c) > 400:
                    continue
                hedged = bool(HEDGE.search(line[:m.start()])) or line.rstrip().endswith("?") \
                    or bool(re.match(r"(?i)(?:not\b(?!\s+applicable)|no longer\b)", c)) \
                    or " or " in c or "?" in c
                hits.append((m.start(), "strict" if rx in STRICT else "broad", c, hedged))
        hits.sort()
        seen = set()
        for _, t, c, h in hits:
            if (c, h) not in seen:
                seen.add((c, h))
                out.append({"tier": t, "cand": c, "hedged": h})
    return out


NUM_GOLD = re.compile(r"^[-+$]?\d[\d,]*\.?\d*%?$")
NUM_CAND = re.compile(r"^[-+$€]?\s?\d[\d,]*\.?\d*(?:\.\.\.)?\s*(?:%|percent|EUR|euros?)?$", re.I)


def answer_shaped(cand, gold):
    g = normalise_like_testsh(cand)
    gold = gold.strip()
    # generic noun phrases ("the answer", "the result", "a script", "it", "for X") are not answers
    if re.match(r"(?i)(?:the|a|an|it|this|that|my|its|these|those|them|in|to|for|with|by|on|from|of)\b", g) \
            and not re.match(r"(?i)(?:the|a|an|it|this|that|my|its|in|to|for|with|by|on|from|of)\b", gold):
        return False
    if NUM_GOLD.match(gold.replace(" ", "")):
        return bool(NUM_CAND.match(g))
    if "," in gold:
        n_gold = len([x for x in re.split(r"[,;]", gold) if x.strip()])
        n_c = len([x for x in re.split(r"[,;]", g) if x.strip()])
        return "," in g and n_c <= n_gold + 2 and all(len(x.split()) <= 4 for x in re.split(r"[,;]", g))
    return len(g.split()) <= len(gold.split()) + 2


def accepted(cand, gold):
    g = normalise_like_testsh(cand)
    if not g:
        return False
    try:
        return bool(scorer.question_scorer(g, gold))
    except Exception:
        return False


# Visible-text-only detector for the product (cannot rely on thinking). A turn "fires" if its
# visible text contains a strict-cue candidate, or the visible text's last non-empty line is a
# short bare value (<= 12 words, no trailing colon) -- the shape pi final messages take.
def text_detector(text):
    cands = [d["cand"] for d in extract(text, "strict") if not d["hedged"]]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        last = lines[-1]
        if not last.endswith(":") and len(last.split()) <= 12 and not last.startswith("```") \
                and re.search(r"\d|[A-Z][a-z]+_|\b(?:yes|no|Not Applicable)\b", last):
            cands.append(_clean(last))
    return [c for c in cands if c]
