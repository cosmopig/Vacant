"""Value-visibility helpers: was the scorer-accepted value visible in the run's own record?"""
import re, json
from scorer import question_scorer, extract_numeric

NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*(?:[eE]-?\d+)?")
UNASSESSABLE = {"yes", "no", "not applicable"}
READ_CMD = re.compile(r"^\s*(ls|cat|head|tail|less|more|wc|find|file|du|stat|sed\s+-n|awk\s+'NR)|\bread\b", re.I)


def kind(expected):
    e = expected.strip()
    if e.lower() in UNASSESSABLE:
        return "yesno_na"
    if re.fullmatch(r"-?\$?\d[\d,]*\.?\d*%?", e) and not ("," in e and not re.fullmatch(r"-?\$?\d{1,3}(,\d{3})+(\.\d+)?", e)):
        return "num"
    if "," in e or ";" in e:
        return "list"
    return "str"


def _word_in(item, text):
    return re.search(r"(?<![\w.])" + re.escape(item.strip()) + r"(?![\w])", text, re.I) is not None


def match_text(expected, text):
    """True if the expected (scorer-accepted) value appears in text."""
    k = kind(expected)
    e = expected.strip()
    if k == "num":
        for tok in NUM_RE.findall(text):
            tok2 = tok.rstrip(".,")
            if not tok2 or tok2 in "-":
                continue
            try:
                if question_scorer(tok2.replace(",", "") if tok2.count(",") and not re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", tok2) else tok2, e):
                    return True
            except Exception:
                pass
        return False
    if k == "list":
        items = [x.strip() for x in re.split(r"[,;]", e) if x.strip()]
        return all(_word_in(i, text) for i in items)
    if k == "str":
        if ":" in e:  # 2697 'E:13.57'
            a, b = e.split(":", 1)
            return re.search(r"(?<![\w])" + re.escape(a) + r"\W{0,4}" + re.escape(b), text) is not None
        return _word_in(e, text)
    if k == "yesno_na":
        return False
    return False


def is_short(ch, expected):
    lim = 400 if kind(expected) != "list" else max(400, 3 * len(expected) + 200)
    return len(ch["text"].strip()) <= lim


def visibility(run):
    """Return dict with first turns where the value is visible (tiers)."""
    e = run["expected"]
    k = kind(e)
    out = dict(kind=k, t2_first=None, t1_first=None, t1_assistant_first=None, last_short_match=None, n_chunks=0)
    if k == "yesno_na":
        return out
    cmd_by_id = {c["id"]: c for c in run["pi"]["calls"]}
    last_short = None
    for ch in run["pi"]["chunks"]:
        txt = ch["text"]
        out["n_chunks"] += 1
        m = match_text(e, txt)
        if m and out["t2_first"] is None:
            out["t2_first"] = ch["turn"]
        if ch["role"] == "assistant":
            if m and out["t1_assistant_first"] is None:
                out["t1_assistant_first"] = ch["turn"]
            if m and out["t1_first"] is None:
                out["t1_first"] = ch["turn"]
            continue
        if ch["err"]:
            continue
        call = cmd_by_id.get(ch.get("call_id")) or {}
        cmd = str((call.get("args") or {}).get("command") or "")
        is_read = call.get("name") in ("read", "ls", "find", "grep") or bool(READ_CMD.match(cmd))
        if is_short(ch, e) and not is_read and txt.strip() and not txt.strip().startswith("Successfully wrote"):
            if m and out["t1_first"] is None:
                out["t1_first"] = ch["turn"]
            last_short = (ch["turn"], m)
    out["last_short_match"] = last_short
    return out
