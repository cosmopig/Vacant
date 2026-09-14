# anchor_kind: goal
# anchor: the unlucky tail
# derivation: with four values the 95th percentile rank is ceil(3.8) = 4, the
# largest; with ten values it is ceil(9.5) = 10, also the largest.


def run(solution):
    lines = ["2026-01-01T00:00:0%d GET /t 200 %d" % (i, v)
             for i, v in enumerate([40, 10, 30, 20])]
    got = solution.summarize(lines)["endpoints"][0]["p95_ms"]
    assert got == 40, "args=%r got=%r want=%r" % ("latencies 10,20,30,40", got, 40)

    values = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]
    lines = ["2026-01-01T00:0%d:00Z GET /t 200 %d" % (i, v) for i, v in enumerate(values)]
    got = solution.summarize(lines)["endpoints"][0]["p95_ms"]
    assert got == 95, "args=%r got=%r want=%r" % ("ten latencies", got, 95)
