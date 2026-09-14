# anchor_kind: contract
# anchor: `N` is the 1-based line number on which the offending record starts and the
# header is line 1
# derivation: the reported number must point at the record that is actually wrong,
# even when an earlier record spanned two physical lines.

def run(solution):
    text = 'a,b\n1,"two\nlines"\n3\n'
    try:
        solution.csv_to_jsonl(text)
    except ValueError as exc:
        got = str(exc)
        assert got.startswith("line 4: "), "args=%r got=%r want=%r" % (text, got, "line 4: ...")
        return
    raise AssertionError("args=%r got=%r want=%r" % (text, "no error", "ValueError"))
