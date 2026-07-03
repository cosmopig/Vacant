from vacant import Vacant, HermesBrain

# 腦 = 真 Hermes Agent（自己調 qwopus），vacant 在外層包 verify-fix + 簽章究責
brain = HermesBrain(
    model="qwopus3.6-27b-coder-mtp-nvfp4",
    base_url="http://192.168.76.1:1234/v1",
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
