# anchor_kind: contract
# anchor: When there are no data rows the result is the empty string.
# derivation: an empty file and a header-only file both have zero data rows.

def run(solution):
    for text in ("", "only,a,header\n", "only,a,header"):
        got = solution.csv_to_jsonl(text)
        assert got == "", "args=%r got=%r want=%r" % (text, got, "")
