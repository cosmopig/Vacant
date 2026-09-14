# anchor_kind: goal
# anchor: a secret that appears twice in one line is gone both times
# derivation: the same secret written twice in one line leaves no trace of either
# occurrence.


def run(solution):
    key = "AKIAM1N2B3V4C5X6Z7A8"
    line = "rotating %s to %s now" % (key, key)
    got = solution.redact(line)
    assert key not in got, "args=%r got=%r want=%r" % (line, got, "both copies removed")

    line = "a Authorization: Bearer tok-one b and c mongodb://u:pw-two@h:1/d e"
    got = solution.redact(line)
    assert "tok-one" not in got and "pw-two" not in got, (
        "args=%r got=%r want=%r" % (line, got, "both secrets removed"))
