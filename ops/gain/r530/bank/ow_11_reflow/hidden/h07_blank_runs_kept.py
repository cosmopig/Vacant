# anchor_kind: goal
# anchor: however many there were is however many they want back
# derivation: a run of three blank lines stays three blank lines, and the
# paragraphs around it are still wrapped.


def run(solution):
    text = "first para\n\n\n\nsecond para\n"
    got = solution.reflow(text, 40)
    lines = got.rstrip("\n").split("\n")
    assert lines == ["first para", "", "", "", "second para"], (
        "args=%r got=%r want=%r" % (text, lines,
                                    ["first para", "", "", "", "second para"]))
