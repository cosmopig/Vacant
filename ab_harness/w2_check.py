#!/usr/bin/env python3
"""W2 decisive test, run on the remote: does the stop check fire in
`opencode run` mode, and does a `continue` decision actually reach the model?

Reads the artefacts the run left behind. Prints PASS/FAIL per claim and exits
non-zero if any claim fails, so it can be run in CI.
"""
import collections
import json
import os
import pathlib
import sys

PROJ = pathlib.Path("/home/user1/.vacant/trace/projects")
STUB_LOG = pathlib.Path("/tmp/stub_w2b.jsonl")
SINCE_MIN = int(os.environ.get("SINCE_MIN", "10"))
WINDOW = f"-{SINCE_MIN} minutes"

import subprocess  # noqa: E402

recent = subprocess.run(
    ["find", str(PROJ), "-name", "perf.jsonl", "-newermt", WINDOW],
    capture_output=True, text=True).stdout.split()

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


# ---- 1. a stop event fired -------------------------------------------------
hists = []
for f in recent:
    c = collections.Counter()
    try:
        for line in open(f, errors="replace"):
            try:
                c[json.loads(line).get("event")] += 1
            except Exception:
                pass
    except OSError:
        continue
    if c:
        hists.append((pathlib.Path(f).parent.name, dict(c)))

stops = [(d, h) for d, h in hists if h.get("stop")]
check("1 a stop event fired in opencode run mode", stops,
      f"histograms seen: {hists}")

# ---- 2. a delivery note was written ---------------------------------------
notes = subprocess.run(
    ["find", str(PROJ), "-name", "delivery.json", "-newermt", WINDOW],
    capture_output=True, text=True).stdout.split()
check("2 a delivery note was written", notes, f"{len(notes)} note(s)")

detail_text = ""
if notes:
    try:
        d = json.loads(pathlib.Path(notes[0]).read_text())
        detail_text = json.dumps(d, ensure_ascii=False)
    except Exception as e:
        detail_text = f"<unreadable: {e}>"
check("2b the note says something about the finding",
      bool(detail_text) and detail_text != "{}", detail_text[:200])

# ---- 3. the feedback reached the model ------------------------------------
# The proof is not "the hook ran" but "a SECOND user-prompt request arrived
# whose text is the feedback". Same-prompt repeats are opencode's own
# title/build sub-agents and prove nothing.
prompts = []
if STUB_LOG.exists():
    for line in STUB_LOG.read_text(errors="replace").splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        if (o.get("roles") or [])[-1:] == ["user"]:
            prompts.append(o.get("last_text", ""))
uniq = sorted(set(prompts))
check("3 the model received a prompt that is NOT the original one",
      len(uniq) > 1, f"{len(uniq)} distinct user prompts: "
                      + " | ".join(u[:60] for u in uniq[:4]))

# ---- 4. and that prompt is the finding, not a coincidence ------------------
finding_words = ("test", "suite", "check", "record", "evidence", "re-run",
                 "rerun", "did not", "no test")
matched = [u for u in uniq if any(w in u.lower() for w in finding_words)]
check("4 the delivered prompt carries the finding's wording", matched,
      f"matched: {[m[:80] for m in matched[:2]]}")

print("=" * 74)
print("W2 — stop check in `opencode run` mode")
print("=" * 74)
for n, ok, d in results:
    print(f"  [{'OK  ' if ok else 'FAIL'}] {n}")
    if d:
        print(f"         {d}")
bad = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(bad)} passed, {len(bad)} failed")
sys.exit(1 if bad else 0)
