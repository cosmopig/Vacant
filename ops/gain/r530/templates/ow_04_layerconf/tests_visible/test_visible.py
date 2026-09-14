"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_precedence():
    """Visible check 1: env beats file beats default."""


    def _bank_entry(solution):
        defaults = {"port": 8080, "host": "localhost", "retries": 3}
        file_text = "port = 9090\nhost = example.com\n"
        env = {"APP_PORT": "7000"}
        config = solution.load(defaults, file_text, env)
        got = (config.get("port"), config.get("host"), config.get("retries"))
        want = (7000, "example.com", 3)
        assert got == want, "args=%r got=%r want=%r" % ((defaults, file_text, env), got, want)
    _bank_entry(solution)


def check_v02_provenance():
    """Visible check 2: for any one setting, say where the value came from."""


    def _bank_entry(solution):
        defaults = {"port": 8080, "host": "localhost", "retries": 3}
        file_text = "host = example.com\n"
        env = {"APP_PORT": "7000"}
        config = solution.load(defaults, file_text, env)
        got = (config.source("port"), config.source("host"), config.source("retries"))
        want = ("env", "file", "default")
        assert got == want, "args=%r got=%r want=%r" % ((defaults, file_text, env), got, want)
    _bank_entry(solution)


def check_v03_types_follow_defaults():
    """Visible check 3: a number from a file arrives as a number, not a string."""


    def _bank_entry(solution):
        defaults = {"port": 8080, "ratio": 0.5, "verbose": False, "name": "svc"}
        file_text = "port = 1234\nratio = 2.5\nverbose = true\nname = 99\n"
        config = solution.load(defaults, file_text, {})
        got = config.as_dict()
        want = {"port": 1234, "ratio": 2.5, "verbose": True, "name": "99"}
        assert got == want, "args=%r got=%r want=%r" % (file_text, got, want)
        assert isinstance(got["port"], int), (
            "args=%r got=%r want=%r" % (file_text, type(got["port"]).__name__, "int"))
        assert got["verbose"] is True, "args=%r got=%r want=%r" % (file_text, got["verbose"], True)
    _bank_entry(solution)
