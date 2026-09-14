# anchor_kind: goal
# anchor: Some of the data is not ASCII and has to survive the trip unchanged.
# derivation: non-ASCII values must come back out identical, whatever escaping the
# JSON writer chooses.

import json


def run(solution):
    text = "name,city\n張三,台南\n"
    got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
    want = {"name": "張三", "city": "台南"}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
