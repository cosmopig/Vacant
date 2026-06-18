import sys, tempfile
from pathlib import Path
from collections import Counter
print("[start] vacant-on-Hermes", flush=True)
from vacant.host import Host
from vacant.hermes_substrate import HermesSubstrate
from vacant.tasks import make_task, NICHES
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6
sub = HermesSubstrate(model="google/gemma-4-e4b", toolsets="", timeout=180)
root = Path(tempfile.mkdtemp(prefix="vacant-hermes-"))
h = Host(root, substrate=sub)
req = h.mint("requester", niches=[])
for j in range(2):
    h.mint(f"e{j}", niches=list(NICHES))
correct, picks = [], []
for i in range(N):
    t = make_task(i)
    try:
        oc = req.call(t["niche"], t); ok = oc.correct; ans = oc.answer; via = oc.callee_id[-6:]
    except Exception as e:
        ok = False; ans = f"[err:{type(e).__name__}]"; via = "------"
    correct.append(int(ok)); picks.append(via)
    print(f"  r{i:02d} [{t['niche']:11}] {t['input']:8} -> {ans!r:18} {'OK' if ok else 'x'} via …{via}", flush=True)
acc = sum(correct)/len(correct)
print(f"\n整體正確率 {acc:.0%}  ({sum(correct)}/{N})", flush=True)
print("路由分佈:", dict(Counter(picks)), flush=True)
rb, eb = h.body("requester"), h.body("e0")
print(f"鏈可驗 requester={rb.logbook.verify_chain(rb.public_identity())} e0={eb.logbook.verify_chain(eb.public_identity())}", flush=True)
print(f"腦=Hermes Agent v0.16.0 -> gemma-4-e4b (LM Studio)", flush=True)
