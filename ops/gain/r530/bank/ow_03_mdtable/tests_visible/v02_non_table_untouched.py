"""Visible check 2: prose is not a table, and a document without one is returned as-is."""


def run(solution):
    text = "# Heading\n\nJust a paragraph about nothing.\n\n- a bullet\n"
    got = solution.realign(text)
    assert got == text, "args=%r got=%r want=%r" % (text, got, text)

    mixed = "before\n|h|\n|---|\n|v|\nafter\n"
    got = solution.realign(mixed)
    lines = got.split("\n")
    assert lines[0] == "before", "args=%r got=%r want=%r" % (mixed, lines[0], "before")
    assert lines[4] == "after", "args=%r got=%r want=%r" % (mixed, lines[4], "after")

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_non_table_untouched")
