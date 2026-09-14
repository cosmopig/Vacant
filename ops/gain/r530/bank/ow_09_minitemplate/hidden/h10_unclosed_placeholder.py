# anchor_kind: goal
# anchor: a placeholder that is never closed
# derivation: an opening brace pair with no closing one is a broken template and is
# reported, not copied through.


def run(solution):
    for template in ("hello {{name", "{{a}} and {{b", "{{#each xs}}{{.}}"):
        try:
            solution.render(template, {"name": "x", "a": 1, "b": 2, "xs": [1]})
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "ValueError"))
