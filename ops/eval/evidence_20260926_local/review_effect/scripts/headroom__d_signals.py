"""(d) Which wrong deliveries carried a signal Vacant could legitimately observe from the record alone?
Signals are computed for every delivered run (OK and WR) so precision can be read, not just recall."""
import json, collections, re, sys
sys.path.insert(0, "/tmp/claude-0/review_effect/headroom")
from vis import match_text, kind
from scorer import question_scorer

R = json.load(open("/tmp/claude-0/review_effect/headroom/runs.json"))
EXC = {"5", "70"}
R = [r for r in R if r["task"] not in EXC and r["file"] is not False and r["got"] is not None]


def st(r):
    return "OK" if r["reward"] == 1.0 else "WR"


def calls(r):
    return r["pi"]["calls"]


def last_write_turn(r):
    w = [x["turn"] for x in r["pi"]["writes"]]
    return max(w) if w else None


def failed_step_ignored(r):
    """A tool step failed (not the benign grep-no-match / exit 1 with no output) and no later step succeeded
    running the same program before the answer was written: proxy = the last non-benign error happened after the
    last successful computation that preceded the write."""
    lw = last_write_turn(r) or 999
    last_err = last_ok = None
    for ch in r["pi"]["chunks"]:
        if ch["role"] != "toolResult" or ch["turn"] > lw:
            continue
        t = ch["text"]
        benign = ch["err"] and ("(no output)" in t and "exited with code 1" in t)
        if ch["err"] and not benign:
            last_err = ch["turn"]
        elif not ch["err"] and ch.get("tool") == "bash":
            last_ok = ch["turn"]
    return last_err is not None and (last_ok is None or last_err >= last_ok)


def any_hard_error(r):
    for ch in r["pi"]["chunks"]:
        if ch["role"] == "toolResult" and (ch["err"] and not ("(no output)" in ch["text"] and "exited with code 1" in ch["text"])):
            return True
        if ch["role"] == "toolResult" and "Traceback (most recent call last)" in ch["text"]:
            return True
    return False


SWALLOW = re.compile(r"except[^\n:]*:\s*\n?\s*(pass|return\s+(False|None|0|\[\]|''|\"\")|continue)", re.M)


def swallowed_exception(r):
    for c in calls(r):
        a = c["args"] or {}
        code = str(a.get("command") or a.get("content") or "") + str(a.get("edits") or "")
        if SWALLOW.search(code):
            return True
    return False


def docs_read(r):
    """manual.md opened in full / partially / not at all."""
    full = part = False
    for c in calls(r):
        a = c["args"] or {}
        if c["name"] == "read" and "manual.md" in str(a.get("path", "")):
            if a.get("limit") or a.get("offset"):
                part = True
            else:
                full = True
        elif c["name"] == "bash":
            cmd = str(a.get("command", ""))
            if "manual.md" in cmd:
                if re.search(r"\bcat\b[^|]*manual\.md(?!\s*\|)", cmd) or re.search(r"open\([^)]*manual\.md", cmd):
                    full = True
                else:
                    part = True  # grep/head/sed on the manual
    return "full" if full else "partial" if part else "none"


def unsourced(r):
    """Delivered value never appeared in any tool output (value not traceable to a step)."""
    g = r["got"].strip()
    if g.lower() in ("yes", "no", "not applicable", ""):
        return None
    for ch in r["pi"]["chunks"]:
        if ch["role"] == "toolResult" and not ch["err"]:
            try:
                if match_text(g, ch["text"]):
                    return False
            except Exception:
                pass
    return True


def fmt_mismatch(r):
    g = r["got"].strip(); gl = r["guideline"]; out = []
    if g.lower() == "not applicable":
        return out
    m = re.search(r"rounded to (\d+) decimal", gl)
    if m and re.fullmatch(r"-?\d+(\.\d+)?%?", g):
        n = int(m.group(1)); d = len(g.split(".")[1].rstrip("%")) if "." in g else 0
        if d != n:
            out.append(f"decimals {d}!={n}")
    if re.search(r"just a number|must be the exact number|number rounded", gl) and not re.fullmatch(r"-?\$?[\d,]*\.?\d+%?", g):
        out.append("not a number")
    if "percentage" in gl and "%" in g:
        out.append("has % sign")
    if re.search(r"form 'X\. Y'", gl) and not re.fullmatch(r"[A-Z]\.\s+\S.*", g):
        out.append("not 'X. Y'")
    if re.search(r"either yes or no|must either yes or no|be either yes or no", gl) and g.lower() not in ("yes", "no"):
        out.append("not yes/no")
    if re.search(r"list", gl) and "," not in g and len(g.split()) > 3:
        out.append("list not comma separated")
    if re.search(r"just the (name|country code|column|string)", gl) and len(g.split()) > 3:
        out.append("more than a name")
    return out


def late_write(r):
    """Answer written only at/after a budget reminder (C2 v3), i.e. the delivered file had no step after it."""
    n = r["pi"]["nudges"]; w = [x["turn"] for x in r["pi"]["writes"]]
    return bool(n and w and min(w) >= min(n))


def sent_back(r):
    acts = (r.get("vc") or {}).get("review_actions") or []
    return "continue" in acts


def multi_candidate(r):
    """The run printed >=2 different values that the scorer would each accept as a *different* final answer
    in the same form as the delivered one, in short computed outputs (ambiguity the agent resolved silently)."""
    g = r["got"].strip()
    if kind(g) != "num":
        return None
    vals = set()
    cmd_by_id = {c["id"]: c for c in calls(r)}
    for ch in r["pi"]["chunks"]:
        if ch["role"] != "toolResult" or ch["err"] or len(ch["text"].strip()) > 200:
            continue
        for tok in re.findall(r"-?\d+\.\d+", ch["text"]):
            vals.add(round(float(tok), 2))
    return len(vals) >= 2


SIG = dict(failed_step_ignored=failed_step_ignored, any_hard_error=any_hard_error, swallowed_exception=swallowed_exception,
           manual_not_opened=lambda r: docs_read(r) == "none", manual_only_partial=lambda r: docs_read(r) == "partial",
           unsourced_value=unsourced, format_mismatch=lambda r: bool(fmt_mismatch(r)), late_write_after_reminder=late_write,
           vacant_sent_back=sent_back)

tab = collections.defaultdict(lambda: collections.Counter())
details = collections.defaultdict(list)
for r in R:
    s = st(r)
    for name, f in SIG.items():
        v = f(r)
        if v is None:
            tab[name][(s, "n/a")] += 1
            continue
        tab[name][(s, bool(v))] += 1
        if v and s == "WR":
            details[name].append((r["arm"], r["task"], r["sample"], r["got"][:40], r["expected"][:40], fmt_mismatch(r) if name == "format_mismatch" else ""))
nOK = sum(1 for r in R if st(r) == "OK"); nWR = sum(1 for r in R if st(r) == "WR")
print(f"delivered runs (77 tasks, all arms): OK {nOK}, WR {nWR}")
print(f"{'signal':28s} {'WR flagged':>12s} {'OK flagged':>12s}  precision(WR among flagged)")
for name in SIG:
    t = tab[name]
    wr = t[("WR", True)]; okf = t[("OK", True)]
    wrn = t[("WR", True)] + t[("WR", False)]; okn = t[("OK", True)] + t[("OK", False)]
    prec = wr / (wr + okf) if wr + okf else float("nan")
    print(f"{name:28s} {wr:4d}/{wrn:<4d}({wr/max(wrn,1):.0%}) {okf:4d}/{okn:<4d}({okf/max(okn,1):.0%})  {prec:.2f}")
print("\nper-arm WR counts with any legit signal (excluding late_write and any_hard_error which are weak):")
LEG = ["failed_step_ignored", "swallowed_exception", "manual_not_opened", "unsourced_value", "format_mismatch"]
for arm in ("A", "C1", "C2"):
    wr = [r for r in R if r["arm"] == arm and st(r) == "WR"]
    ok = [r for r in R if r["arm"] == arm and st(r) == "OK"]
    fw = sum(1 for r in wr if any(SIG[s](r) for s in LEG))
    fo = sum(1 for r in ok if any(SIG[s](r) for s in LEG))
    print(f"{arm}: WR {len(wr)} flagged {fw}; OK {len(ok)} flagged {fo}")
for name in ("failed_step_ignored", "swallowed_exception", "unsourced_value", "format_mismatch", "manual_not_opened"):
    print(f"\n-- WR with {name} --")
    for d in details[name][:40]:
        print("  ", d)
json.dump({k: dict((str(kk), vv) for kk, vv in v.items()) for k, v in tab.items()}, open("/tmp/claude-0/review_effect/headroom/d_table.json", "w"), indent=1)
