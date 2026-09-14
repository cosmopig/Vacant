# anchor_kind: goal
# anchor: except for plain bytes, which are whole things and should look like it
# derivation: anything below one step prints as an integer with the byte unit and
# no decimal point anywhere.


def run(solution):
    for number in (0, 1, 7, 512, 999, 1023):
        got = solution.humanize(number)
        assert got == "%d B" % number, "args=%r got=%r want=%r" % (number, got, "%d B" % number)
        assert "." not in got, "args=%r got=%r want=%r" % (number, got, "no decimal point")
