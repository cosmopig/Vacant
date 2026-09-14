# anchor_kind: goal
# anchor: their templates sometimes have to print two literal braces
# derivation: the escaped form renders as the braces themselves, the backslash
# disappears, and what follows is ordinary text rather than a placeholder.


def run(solution):
    template = "\\{{name}} is how you write {{name}}"
    data = {"name": "Ann"}
    got = solution.render(template, data)
    want = "{{name}} is how you write Ann"
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
