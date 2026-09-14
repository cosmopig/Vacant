# anchor_kind: goal
# anchor: whole columns left blank
# derivation: a column nobody filled in yields the empty string on every row, and a
# record whose fields are all empty is still a record.

import json


def run(solution):
    text = "a,b,c\n1,,x\n,,\n"
    lines = solution.csv_to_jsonl(text).splitlines()
    assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
    first, second = json.loads(lines[0]), json.loads(lines[1])
    assert first == {"a": "1", "b": "", "c": "x"}, (
        "args=%r got=%r want=%r" % (text, first, {"a": "1", "b": "", "c": "x"}))
    assert second == {"a": "", "b": "", "c": ""}, (
        "args=%r got=%r want=%r" % (text, second, {"a": "", "b": "", "c": ""}))
