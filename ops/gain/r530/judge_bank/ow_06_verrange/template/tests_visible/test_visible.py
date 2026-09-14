"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_numbers_are_numbers():
    """Visible check 1: the three numbers sort as numbers, not as text."""


    def _bank_entry(solution):
        cases = [("1.10.0", "1.9.0", 1), ("1.9.0", "1.10.0", -1), ("2.0.0", "2.0.0", 0),
                 ("1.2.3", "1.2.4", -1), ("10.0.0", "9.99.99", 1)]
        for a, b, want in cases:
            got = solution.compare(a, b)
            assert got == want, "args=%r got=%r want=%r" % ((a, b), got, want)
    _bank_entry(solution)


def check_v02_prerelease_is_older():
    """Visible check 2: a pre-release is older than the release it leads up to."""


    def _bank_entry(solution):
        got = solution.compare("1.0.0-rc1", "1.0.0")
        assert got == -1, "args=%r got=%r want=%r" % (("1.0.0-rc1", "1.0.0"), got, -1)
        got = solution.compare("1.0.0", "1.0.0-rc1")
        assert got == 1, "args=%r got=%r want=%r" % (("1.0.0", "1.0.0-rc1"), got, 1)
        got = solution.compare("1.0.0-rc1", "1.0.0-rc1")
        assert got == 0, "args=%r got=%r want=%r" % (("1.0.0-rc1", "1.0.0-rc1"), got, 0)
    _bank_entry(solution)


def check_v03_spec_conditions():
    """Visible check 3: a requirement with two conditions, both of which must hold."""


    def _bank_entry(solution):
        got = solution.satisfies("1.4.2", ">=1.4.0,<2.0.0")
        assert got is True, "args=%r got=%r want=%r" % (("1.4.2", ">=1.4.0,<2.0.0"), got, True)
        got = solution.satisfies("2.0.1", ">=1.4.0,<2.0.0")
        assert got is False, "args=%r got=%r want=%r" % (("2.0.1", ">=1.4.0,<2.0.0"), got, False)
        got = solution.satisfies("1.3.9", ">=1.4.0,<2.0.0")
        assert got is False, "args=%r got=%r want=%r" % (("1.3.9", ">=1.4.0,<2.0.0"), got, False)
    _bank_entry(solution)
