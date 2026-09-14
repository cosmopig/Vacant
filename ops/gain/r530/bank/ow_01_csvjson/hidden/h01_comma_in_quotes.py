# anchor_kind: goal
# anchor: fields containing commas
# derivation: a hand-edited field that holds commas must arrive as one value, not several.

import json


def run(solution):
    text = 'id,addr\n7,"12 Main St, Apt 4, Rear"\n'
    got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
    want = {"id": "7", "addr": "12 Main St, Apt 4, Rear"}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
