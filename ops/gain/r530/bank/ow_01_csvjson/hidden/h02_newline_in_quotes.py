# anchor_kind: goal
# anchor: fields containing line breaks
# derivation: a line break inside a quoted field belongs to the value, so the record
# spans two physical lines and still produces one object.

import json


def run(solution):
    text = 'id,memo\n9,"first\nsecond"\n10,plain\n'
    out = solution.csv_to_jsonl(text)
    lines = out.splitlines()
    assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
    got = json.loads(lines[0])
    want = {"id": "9", "memo": "first\nsecond"}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
