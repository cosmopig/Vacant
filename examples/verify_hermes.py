import os

from vacant import Vacant, HermesBrain

# 腦 = 真 Hermes Agent（自己調 qwopus），vacant 在外層包 verify-fix + 簽章究責
# 端點不寫死（G10）：VACANT_ENDPOINT 指定，預設本機 LM Studio
brain = HermesBrain(
    model="qwopus3.6-27b-coder-mtp-nvfp4",
    base_url=os.environ.get("VACANT_ENDPOINT", "http://localhost:1234").rstrip("/") + "/v1",
    timeout=220,
)
v = Vacant(brain, k=2)

def norm(a):
    return a.strip().strip('"').strip("'").split("\n")[-1].strip()

cases = [("cvve2f", "f2evvc"), ("hello1", "1olleh")]
for inp, exp in cases:
    r = v.solve(
        f"Reverse this string and output ONLY the reversed characters, nothing else: {inp}",
        verifier=(lambda a, _e=exp: norm(a) == _e),
    )
    print(f"  {inp:8} -> verified={r.verified} calls={r.calls} answer={norm(r.answer)!r}", flush=True)

print("RESULT brain=%s accountable_chain=%s logbook_entries=%d" % (
    brain.name, v.verify_chain(), len(v.logbook)))
