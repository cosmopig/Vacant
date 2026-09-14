"""Visible check 3: a requirement with two conditions, both of which must hold."""


def run(solution):
    got = solution.satisfies("1.4.2", ">=1.4.0,<2.0.0")
    assert got is True, "args=%r got=%r want=%r" % (("1.4.2", ">=1.4.0,<2.0.0"), got, True)
    got = solution.satisfies("2.0.1", ">=1.4.0,<2.0.0")
    assert got is False, "args=%r got=%r want=%r" % (("2.0.1", ">=1.4.0,<2.0.0"), got, False)
    got = solution.satisfies("1.3.9", ">=1.4.0,<2.0.0")
    assert got is False, "args=%r got=%r want=%r" % (("1.3.9", ">=1.4.0,<2.0.0"), got, False)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_spec_conditions")
