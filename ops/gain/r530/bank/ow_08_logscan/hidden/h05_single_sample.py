# anchor_kind: contract
# anchor: Percentiles are nearest-rank
# derivation: with one value the rank is 1 for every percentile, so both numbers are
# that value.


def run(solution):
    lines = ["2026-01-01T00:00:00Z POST /only 200 77"]
    got = solution.summarize(lines)["endpoints"][0]
    assert (got["p50_ms"], got["p95_ms"]) == (77, 77), (
        "args=%r got=%r want=%r" % (lines, (got["p50_ms"], got["p95_ms"]), (77, 77)))
