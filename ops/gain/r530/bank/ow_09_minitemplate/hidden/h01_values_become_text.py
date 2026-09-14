# anchor_kind: contract
# anchor: converted with `str()`
# derivation: numbers, booleans and None all arrive as their str() form rather
# than being rejected or formatted some other way.


def run(solution):
    template = "{{n}}|{{f}}|{{b}}|{{z}}"
    data = {"n": 42, "f": 1.5, "b": True, "z": None}
    got = solution.render(template, data)
    want = "42|1.5|True|None"
    assert got == want, "args=%r got=%r want=%r" % ((template, data), got, want)
