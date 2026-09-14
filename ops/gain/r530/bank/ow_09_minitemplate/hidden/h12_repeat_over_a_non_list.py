# anchor_kind: goal
# anchor: a repeat over something that is not a list
# derivation: a string or a dictionary is not a list, so repeating over one is a
# template mistake rather than an iteration over characters or keys.


def run(solution):
    for value in ("abc", {"a": 1}, 7):
        template = "{{#each thing}}{{.}}{{/each}}"
        try:
            solution.render(template, {"thing": value})
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (value, "rendered", "ValueError"))
