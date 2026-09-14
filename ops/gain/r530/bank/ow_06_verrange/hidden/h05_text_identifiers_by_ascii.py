# anchor_kind: goal
# anchor: alpha comes before beta
# derivation: identifiers that are not all digits sort the way their characters
# sort.


def run(solution):
    got = solution.compare("2.1.0-alpha", "2.1.0-beta")
    assert got == -1, "args=%r got=%r want=%r" % (("2.1.0-alpha", "2.1.0-beta"), got, -1)
    got = solution.compare("2.1.0-beta", "2.1.0-rc")
    assert got == -1, "args=%r got=%r want=%r" % (("2.1.0-beta", "2.1.0-rc"), got, -1)
