# anchor_kind: goal
# anchor: a pre-release with more parts is newer than the same pre-release with
# fewer
# derivation: when every shared identifier matches, the one carrying an extra
# identifier is the newer of the two.


def run(solution):
    got = solution.compare("1.0.0-rc.1.2", "1.0.0-rc.1")
    assert got == 1, "args=%r got=%r want=%r" % (("1.0.0-rc.1.2", "1.0.0-rc.1"), got, 1)
    got = solution.compare("1.0.0-alpha", "1.0.0-alpha.1")
    assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-alpha", "1.0.0-alpha.1"), got, -1)
