# anchor_kind: goal
# anchor: a closing repeat with nothing to close
# derivation: a closing tag on its own, and an item reference outside any block,
# are both template mistakes.


def run(solution):
    for template in ("text {{/each}} more", "{{.}}", "{{.field}}"):
        try:
            solution.render(template, {"field": 1})
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "ValueError"))
