"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_values_and_groups():
    """Visible check 1: the five kinds of value, and a group."""


    def _bank_entry(solution):
        text = 'name = "billing"\nport = 8080\nratio = 0.25\ndebug = false\n\n[db]\nhost = "db.internal"\n'
        got = solution.parse(text)
        want = {"name": "billing", "port": 8080, "ratio": 0.25, "debug": False,
                "db": {"host": "db.internal"}}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
        assert isinstance(got["port"], int) and got["debug"] is False, (
            "args=%r got=%r want=%r" % (text, (type(got["port"]).__name__, got["debug"]), ("int", False)))
    _bank_entry(solution)


def check_v02_lists_and_comments():
    """Visible check 2: lists of one kind, and comments that are not settings."""


    def _bank_entry(solution):
        text = ("# the ports we listen on\nports = [80, 443, 8080]   # and nothing else\n"
                "\nnames = [\"a\", \"b\"]\nempty = []\n")
        got = solution.parse(text)
        want = {"ports": [80, 443, 8080], "names": ["a", "b"], "empty": []}
        assert got == want, "args=%r got=%r want=%r" % (text, got, want)
    _bank_entry(solution)


def check_v03_round_trip():
    """Visible check 3: out and back again gives the same data."""


    def _bank_entry(solution):
        data = {"name": "svc", "retries": 3,
                "db": {"host": "h", "port": 5432}}
        text = solution.dumps(data)
        got = solution.parse(text)
        assert got == data, "args=%r got=%r want=%r" % (text, got, data)
    _bank_entry(solution)
