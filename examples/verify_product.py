from vacant import Vacant, LMStudioBrain

BASE = "http://192.168.76.1:1234"
MODEL = "gemma-4-12b-coder-fable5-composer2.5-v1"

brain = LMStudioBrain(BASE, MODEL, api="responses")
v = Vacant(brain, k=3)

def norm(a):
    return a.strip().strip('"').strip("'")

cases = [("hello", "olleh"), ("world", "dlrow"), ("abc123", "321cba")]
for inp, exp in cases:
    r = v.solve(
        f"Reverse this string, output ONLY the reversed characters: {inp}",
        verifier=(lambda a, _e=exp: norm(a) == _e),
    )
    print(f"  {inp:8} -> verified={r.verified} calls={r.calls} answer={r.answer!r}")

print("RESULT accountable_chain=%s logbook_entries=%d brain=%s" % (
    v.verify_chain(), len(v.logbook), brain.name))
