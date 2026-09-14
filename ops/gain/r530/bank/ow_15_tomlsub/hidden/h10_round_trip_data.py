# anchor_kind: goal
# anchor: Writing the data out and reading it back has to give the same data
# derivation: data holding every kind, including text that needs escaping and a
# nested group, survives a trip through the written form.


def run(solution):
    data = {"title": 'a "quoted"\ttitle', "n": -3, "f": 1.25, "yes": True, "no": False,
            "ports": [1, 2, 3], "words": ["a", "b"], "none": [],
            "outer": {"inner": {"deep": "yes"}, "k": 1}}
    written = solution.dumps(data)
    got = solution.parse(written)
    assert got == data, "args=%r got=%r want=%r" % (written, got, data)
