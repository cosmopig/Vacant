# anchor_kind: goal
# anchor: they need both the item itself and its fields
# derivation: a list of plain values is reached through the lone dot, with the
# block text repeated around each one.


def run(solution):
    template = "{{#each words}}[{{.}}]{{/each}}"
    data = {"words": ["a", "bb", 3]}
    got = solution.render(template, data)
    want = "[a][bb][3]"
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
