# anchor_kind: goal
# anchor: rc.2 comes after rc.1
# derivation: an identifier made of digits is a number, so rc.10 is newer than
# rc.2 even though the text sorts the other way.


def run(solution):
    got = solution.compare("1.0.0-rc.2", "1.0.0-rc.1")
    assert got == 1, "args=%r got=%r want=%r" % (("1.0.0-rc.2", "1.0.0-rc.1"), got, 1)
    got = solution.compare("1.0.0-rc.10", "1.0.0-rc.2")
    assert got == 1, "args=%r got=%r want=%r" % (("1.0.0-rc.10", "1.0.0-rc.2"), got, 1)
