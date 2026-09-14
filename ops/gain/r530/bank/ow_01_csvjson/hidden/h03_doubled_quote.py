# anchor_kind: contract
# anchor: inside such a field a doubled `""` stands for one literal double quote
# derivation: the escape has to collapse to exactly one quote character.

import json


def run(solution):
    text = 'who,said\nann,"she said ""no"" twice"\n'
    got = json.loads(solution.csv_to_jsonl(text).splitlines()[0])
    want = {"who": "ann", "said": 'she said "no" twice'}
    assert got == want, "args=%r got=%r want=%r" % (text, got, want)
