"""Visible check 3: asking for something the data has not got is an error."""


def run(solution):
    template = "Hello {{who}}"
    data = {"other": 1}
    try:
        solution.render(template, data)
    except KeyError as exc:
        assert exc.args[0] == "who", "args=%r got=%r want=%r" % (template, exc.args[0], "who")
        return
    raise AssertionError("args=%r got=%r want=%r" % ((template, data), "rendered", "KeyError"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_missing_key_is_loud")
