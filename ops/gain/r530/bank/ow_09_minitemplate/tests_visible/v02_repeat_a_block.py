"""Visible check 2: a block repeated once per item in a list."""


def run(solution):
    template = "{{#each rows}}- {{.label}}\n{{/each}}"
    data = {"rows": [{"label": "one"}, {"label": "two"}]}
    got = solution.render(template, data)
    want = "- one\n- two\n"
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_repeat_a_block")
