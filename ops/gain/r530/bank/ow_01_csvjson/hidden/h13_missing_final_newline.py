# anchor_kind: contract
# anchor: The input may or may not end with a final newline; that makes no
# difference to the output.
# derivation: the same data with and without a trailing newline must convert
# identically, including the newline the output itself must end with.

def run(solution):
    with_nl = "u,v\n5,6\n7,8\n"
    without = "u,v\n5,6\n7,8"
    a = solution.csv_to_jsonl(with_nl)
    b = solution.csv_to_jsonl(without)
    assert a == b, "args=%r got=%r want=%r" % (without, b, a)
    assert b.endswith("\n"), "args=%r got=%r want=%r" % (without, b, "ends with a newline")
