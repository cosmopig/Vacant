# anchor_kind: goal
# anchor: Every mistake has to say which line it is on
# derivation: several different kinds of malformed line each report the line they
# are on, counting comments and blank lines.


def run(solution):
    cases = [('# note\n\na = 1\nthis is junk\n', "line 4: "),
             ('a = 1\nb = \n', "line 2: "),
             ('a = 1\nb = [1, 2\n', "line 2: "),
             ('a = 1\n[unclosed\n', "line 2: "),
             ('a = 1\nb = notaword\n', "line 2: ")]
    for text, prefix in cases:
        try:
            solution.parse(text)
        except ValueError as exc:
            assert str(exc).startswith(prefix), (
                "args=%r got=%r want=%r" % (text, str(exc), prefix + "..."))
            continue
        raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))
