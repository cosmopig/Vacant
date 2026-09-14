"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_reads_sizes():
    """Visible check 1: the written forms turn into byte counts."""


    def _bank_entry(solution):
        cases = [("1.5 KiB", 1536), ("10MB", 10000000), ("512", 512), ("3 b", 3)]
        for text, want in cases:
            got = solution.to_bytes(text)
            assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_v02_prints_sizes():
    """Visible check 2: byte counts turn back into the written forms."""


    def _bank_entry(solution):
        cases = [(1536, True, "1.5 KiB"), (1500000, False, "1.5 MB"), (3 * 1024 ** 3, True, "3.0 GiB")]
        for number, binary, want in cases:
            got = solution.humanize(number, binary=binary)
            assert got == want, "args=%r got=%r want=%r" % ((number, binary), got, want)
    _bank_entry(solution)


def check_v03_refuses_nonsense():
    """Visible check 3: what cannot be read is refused."""


    def _bank_entry(solution):
        for text in ("", "   ", "banana", "4 KBs", "1.2.3 MB"):
            try:
                solution.to_bytes(text)
            except ValueError:
                continue
            raise AssertionError("args=%r got=%r want=%r" % (text, "a number", "ValueError"))
    _bank_entry(solution)
