# anchor_kind: goal
# anchor: silently producing an empty string is what bit them last time
# derivation: every way of missing a value -- a top-level name, a path through a
# non-dictionary, a field of an item -- raises rather than rendering nothing.


def run(solution):
    cases = [("{{nope}}", {}), ("{{a.b}}", {"a": 5}),
             ("{{#each xs}}{{.q}}{{/each}}", {"xs": [{"p": 1}]})]
    for template, data in cases:
        try:
            solution.render(template, data)
        except KeyError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % ((template, data), "rendered", "KeyError"))
