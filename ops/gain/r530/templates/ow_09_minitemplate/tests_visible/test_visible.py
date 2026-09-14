"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_placeholders():
    """Visible check 1: plain and nested placeholders, values turned into text."""


    def _bank_entry(solution):
        template = "Hi {{user.name}}, you have {{count}} messages."
        data = {"user": {"name": "Ann"}, "count": 3}
        got = solution.render(template, data)
        want = "Hi Ann, you have 3 messages."
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_v02_repeat_a_block():
    """Visible check 2: a block repeated once per item in a list."""


    def _bank_entry(solution):
        template = "{{#each rows}}- {{.label}}\n{{/each}}"
        data = {"rows": [{"label": "one"}, {"label": "two"}]}
        got = solution.render(template, data)
        want = "- one\n- two\n"
        assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
    _bank_entry(solution)


def check_v03_missing_key_is_loud():
    """Visible check 3: asking for something the data has not got is an error."""


    def _bank_entry(solution):
        template = "Hello {{who}}"
        data = {"other": 1}
        try:
            solution.render(template, data)
        except KeyError as exc:
            assert exc.args[0] == "who", "args=%r got=%r want=%r" % (template, exc.args[0], "who")
            return
        raise AssertionError("args=%r got=%r want=%r" % ((template, data), "rendered", "KeyError"))
    _bank_entry(solution)
