# anchor_kind: goal
# anchor: a repeat inside a repeat
# derivation: nesting the blocks is outside the language and is reported rather
# than half-rendered.


def run(solution):
    template = "{{#each rows}}{{#each inner}}{{.}}{{/each}}{{/each}}"
    data = {"rows": [{"inner": [1]}], "inner": [1]}
    try:
        solution.render(template, data)
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r" % (template, "rendered", "ValueError"))
