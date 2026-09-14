# anchor_kind: contract
# anchor: When a header name repeats, the last occurrence wins.
# derivation: two columns called the same thing collapse to one key holding the
# rightmost column's value.

import json


def run(solution):
    text = "k,v,k\nalpha,1,omega\n"
    got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
    want = {"k": "omega", "v": "1"}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
