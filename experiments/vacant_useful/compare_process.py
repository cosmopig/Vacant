"""Compare process metrics: baseline vs vacant runs with SYNTHETIC example profiles.

python compare_process.py BASELINE_DIR CAUTIOUS_DIR FAST_DIR
Reads each run's metrics.json (PR #92 harness). Scope drift (T3): original public
names of utils.py missing afterwards, or `import app` fails. Outcome: pytest in ws
(T1/T2 where tests exist). Personas are SYNTHETIC examples, not a real user.
"""
import json, subprocess, sys
from pathlib import Path
PYTEST = "/workspace/process_baseline/agentenv/bin/python"
PUBLIC = ["ReadCfg", "slug", "slug2", "chunks"]
def check(rdir, task):
    ws = rdir / "ws"; out = {}
    if task.startswith("T3"):
        src = (ws / "utils.py").read_text() if (ws / "utils.py").exists() else ""
        missing = [n for n in PUBLIC if f"def {n}(" not in src and f"{n} =" not in src]
        imp = subprocess.run([sys.executable, "-c", "import app"], cwd=ws, capture_output=True).returncode == 0
        out["scope_drift"] = bool(missing) or not imp
    if (ws / "tests").exists():
        out["tests_pass"] = subprocess.run([PYTEST, "-m", "pytest", "-q", "-x", "tests"], cwd=ws, capture_output=True, timeout=120).returncode == 0
    return out
def load(d):
    rows = []
    for m in sorted(Path(d).glob("*/metrics.json")):
        r = json.loads(m.read_text()); r.update(check(m.parent, r["task_id"])); rows.append(r)
    return rows
def frac(xs):
    xs = [x for x in xs if x is not None]
    return f"{sum(bool(x) for x in xs)}/{len(xs)}" if xs else "-"
def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return f"{sum(xs)/len(xs):.3f} (n={len(xs)})" if xs else "-"
conds = dict(zip(["baseline", "vacant+cautious(SYNTH)", "vacant+fast(SYNTH)"], sys.argv[1:4]))
print("| metric | " + " | ".join(conds) + " |"); print("|---|" + "---|" * len(conds))
data = {c: load(d) for c, d in conds.items()}
def row(label, fn):
    print(f"| {label} | " + " | ".join(fn(v) for v in data.values()) + " |")
row("runs", lambda v: str(len(v)))
row("asked user (harness A-step)", lambda v: frac([r["features"]["asked_any"] for r in v]))
KW = ("question", "should ", "let me know", "your input", "would you", "do you want", "prefer")
def asks(r):
    t = (r.get("final_text") or "").lower()
    return r["features"]["asked_any"] or ("?" in t and any(k in t for k in KW) and not r["features"]["made_edit"])
row("stopped to ask before editing (final text asks, no edit)", lambda v: frac([asks(r) for r in v]))
row("asked on T2 (ambiguous feature)", lambda v: frac([asks(r) for r in v if r["task_id"].startswith("T2")]))
row("made an edit", lambda v: frac([r["features"]["made_edit"] for r in v]))
row("test before first edit (runs that edited)", lambda v: frac([r["features"]["test_before_first_edit"] for r in v]))
row("test after last edit (runs that edited)", lambda v: frac([r["features"]["test_after_last_edit"] for r in v]))
row("T3 scope drift (public name removed / import fails)", lambda v: frac([r.get("scope_drift") for r in v if r["task_id"].startswith("T3")]))
row("tests pass at end (T1/T2)", lambda v: frac([r.get("tests_pass") for r in v if r["task_id"][:2] in ("T1", "T2")]))
row("mean steps", lambda v: mean([r["features"]["n_steps"] for r in v]))
row("mean diff lines (+/-)", lambda v: mean([r["features"]["diff_added"] + r["features"]["diff_removed"] for r in v]))
for p in ("example_cautious", "example_fast"):
    row(f"order similarity to {p} (collapsed edit sim)", lambda v, p=p: mean([r.get("persona_similarity", {}).get(p, {}).get("edit_sim_collapsed") for r in v]))
    row(f"feature agreement with {p}", lambda v, p=p: mean([r.get("persona_similarity", {}).get(p, {}).get("feature_agreement") for r in v]))
print()
for c, v in data.items():
    print(f"- {c}: " + ", ".join(f"{r['task_id'][:2]} `{r['sequence']}`" for r in v))
