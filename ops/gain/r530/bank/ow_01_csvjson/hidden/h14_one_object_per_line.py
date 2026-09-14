# anchor_kind: contract
# anchor: one JSON object per data row, each object on its own line
# derivation: three data rows give three lines, each of which parses on its own as
# one object whose values are all strings.

import json


def run(solution):
    text = "n\n1\n2\n3\n"
    got = solution.csv_to_jsonl(text)
    lines = got.splitlines()
    assert len(lines) == 3, "args=%r got=%r want=%r" % (text, len(lines), 3)
    for line in lines:
        obj = json.loads(line)
        assert isinstance(obj, dict), "args=%r got=%r want=%r" % (text, type(obj).__name__, "dict")
        for value in obj.values():
            assert isinstance(value, str), (
                "args=%r got=%r want=%r" % (text, type(value).__name__, "str"))
