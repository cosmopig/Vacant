# anchor_kind: goal
# anchor: a value that cannot be turned into the right kind of thing must fail
# loudly rather than becoming a zero
# derivation: a word that is not one of the accepted boolean spellings must raise
# rather than quietly become False.


def run(solution):
    defaults = {"flag": True}
    file_text = "flag = maybe\n"
    try:
        solution.load(defaults, file_text, {})
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r" % (file_text, "no error", "ValueError"))
