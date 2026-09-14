# anchor_kind: contract
# anchor: `"\n"` and `"\r\n"` are both accepted as line endings and neither survives
# derivation: a file last saved on Windows must not leave a stray carriage return
# glued to the final value of every row.

import json


def run(solution):
    text = "x,y\r\n1,2\r\n3,4\r\n"
    lines = solution.csv_to_jsonl(text).splitlines()
    assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
    got = [json.loads(line) for line in lines]
    want = [{"x": "1", "y": "2"}, {"x": "3", "y": "4"}]
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
