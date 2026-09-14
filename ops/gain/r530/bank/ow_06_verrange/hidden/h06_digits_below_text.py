# anchor_kind: contract
# anchor: an all-digit identifier is older than one that is not
# derivation: at the same position a numeric identifier loses to a textual one, so
# 1.0.0-1 is older than 1.0.0-alpha.


def run(solution):
    got = solution.compare("1.0.0-1", "1.0.0-alpha")
    assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-1", "1.0.0-alpha"), got, -1)
    got = solution.compare("1.0.0-rc.5", "1.0.0-rc.beta")
    assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-rc.5", "1.0.0-rc.beta"), got, -1)
