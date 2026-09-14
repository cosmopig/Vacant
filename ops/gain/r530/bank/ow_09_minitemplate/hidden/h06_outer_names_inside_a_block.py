# anchor_kind: goal
# anchor: they still need to reach the values that live outside the block
# derivation: a name without a leading dot is looked up in the outer data even
# while a block is being repeated.


def run(solution):
    template = "{{#each rows}}{{title}}:{{.n}} {{/each}}"
    data = {"title": "T", "rows": [{"n": 1}, {"n": 2}]}
    got = solution.render(template, data)
    want = "T:1 T:2 "
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
