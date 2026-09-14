"""Visible check 3: the separator row keeps the alignment it was given."""


def run(solution):
    text = "| l | c | r |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n"
    got = solution.realign(text)
    sep = got.split("\n")[1]
    cells = [c.strip() for c in sep.strip().strip("|").split("|")]
    assert cells[0].startswith(":") and not cells[0].endswith(":"), (
        "args=%r got=%r want=%r" % (text, cells[0], "left marker kept"))
    assert cells[1].startswith(":") and cells[1].endswith(":"), (
        "args=%r got=%r want=%r" % (text, cells[1], "centre marker kept"))
    assert cells[2].endswith(":") and not cells[2].startswith(":"), (
        "args=%r got=%r want=%r" % (text, cells[2], "right marker kept"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_alignment_markers")
