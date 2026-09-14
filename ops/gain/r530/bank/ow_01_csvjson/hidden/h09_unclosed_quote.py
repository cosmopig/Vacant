# anchor_kind: contract
# anchor: Invalid means: a record whose field count differs from the header, or an
# unclosed quote.
# derivation: a quote that is never closed is an error, not a value that runs to the
# end of the file.

def run(solution):
    text = 'a,b\n1,"never closed\n'
    try:
        solution.csv_to_jsonl(text)
    except ValueError as exc:
        got = str(exc)
        assert got.startswith("line 2: "), "args=%r got=%r want=%r" % (text, got, "line 2: ...")
        return
    raise AssertionError("args=%r got=%r want=%r" % (text, "no error", "ValueError"))
