import os, tempfile
from pathlib import Path
from vacant.host import Host
from vacant.composer import Composer
from vacant.verifier import is_correct
from vacant.tasks import task_stream, NICHES
from vacant.openai_substrate import ResponsesSubstrate

# 端點不寫死（G10）：VACANT_ENDPOINT 指定，預設本機 LM Studio
URL = os.environ.get("VACANT_ENDPOINT", "http://localhost:1234").rstrip("/") + "/v1"
MODEL = "gemma-4-12b-coder-fable5-composer2.5-v1"
N, K = 6, 2
sub = ResponsesSubstrate(URL, model=MODEL, timeout=75, learn=False)
h = Host(Path(tempfile.mkdtemp(prefix="vc-")), substrate=sub)
h.mint("req", niches=[]); h.mint("expert", niches=list(NICHES))
eid = h.vacant_id("expert")

def make_gen(task):
    def gen(fb):
        t = dict(task); t["feedback"] = fb
        try:
            return h.waker.wake(eid, t["prompt"], t).result.output
        except Exception as e:
            return f"[err:{type(e).__name__}]"
    return gen

stats = {"plain": [0, 0], "naive": [0, 0], "vacant": [0, 0]}
strat = [("plain", lambda c: c.plain()), ("naive", lambda c: c.naive(K)), ("vacant", lambda c: c.vacant(K))]
for i, task in enumerate(task_stream(N)):
    chk = lambda a, _t=task: is_correct(_t, a)
    row = {}
    for name, fn in strat:
        r = fn(Composer(make_gen(task), chk))
        stats[name][0] += int(r.correct); stats[name][1] += r.calls
        row[name] = ("OK" if r.correct else "x") + f"({r.calls})"
    print(f"t{i} [{task['niche']:11}] plain={row['plain']:6} naive={row['naive']:6} vacant={row['vacant']:6}", flush=True)

print("RESULTS")
for name in ("plain", "naive", "vacant"):
    hh, cc = stats[name]
    print("  %-7s acc=%.0f%%  calls/task=%.1f" % (name, hh / N * 100, cc / N))
pa, na, va = stats["plain"][0] / N, stats["naive"][0] / N, stats["vacant"][0] / N
print("  vacant-plain=%+.0f%%   vacant-naive=%+.0f%%" % ((va - pa) * 100, (va - na) * 100))
