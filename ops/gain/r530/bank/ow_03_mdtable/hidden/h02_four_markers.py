# anchor_kind: contract
# anchor: A separator cell keeps the alignment markers it had
# derivation: all four markers appear in one table and all four have to survive,
# each stretched to its own column width.


def run(solution):
    text = "| plain | left | right | centre |\n| --- | :--- | ---: | :---: |\n| aaaaaa | b | c | d |\n"
    got = solution.realign(text)
    sep = got.split("\n")[1]
    cells = [c.strip() for c in sep.strip().strip("|").split("|")]
    shapes = [(c.startswith(":"), c.endswith(":") and len(c) >= 2) for c in cells]
    want = [(False, False), (True, False), (False, True), (True, True)]
    assert shapes == want, "args=%r got=%r want=%r" % (text, shapes, want)
    assert all("-" in c for c in cells), "args=%r got=%r want=%r" % (text, cells, "each keeps dashes")
