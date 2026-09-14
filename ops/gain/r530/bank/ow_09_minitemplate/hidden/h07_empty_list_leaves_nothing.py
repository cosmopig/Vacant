# anchor_kind: goal
# anchor: An empty list should leave nothing behind.
# derivation: the block contributes no output at all, while the text around it is
# still rendered.


def run(solution):
    template = "start|{{#each rows}}x{{.}}x{{/each}}|end"
    data = {"rows": []}
    got = solution.render(template, data)
    want = "start||end"
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
