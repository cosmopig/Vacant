# anchor_kind: contract
# anchor: the p-th percentile of n sorted values is the one at 1-based position
# `ceil(p / 100 * n)`
# derivation: with four values the median rank is ceil(2.0) = 2, which is the
# second smallest -- a floor-indexed implementation returns the third.


def run(solution):
    lines = ["2026-01-01T00:00:0%d GET /m 200 %d" % (i, v)
             for i, v in enumerate([40, 10, 30, 20])]
    got = solution.summarize(lines)["endpoints"][0]["p50_ms"]
    assert got == 20, "args=%r got=%r want=%r" % ("latencies 10,20,30,40", got, 20)
