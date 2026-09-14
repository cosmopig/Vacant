"""Visible check 2: when two patterns fit, the more specific one answers."""


def run(solution):
    router = solution.Router()
    router.add("/users/{id}", "show")
    router.add("/users/new", "create_form")
    got = router.match("/users/new")
    assert got == ("create_form", {}), (
        "args=%r got=%r want=%r" % ("/users/new", got, ("create_form", {})))
    got = router.match("/users/7")
    assert got == ("show", {"id": "7"}), (
        "args=%r got=%r want=%r" % ("/users/7", got, ("show", {"id": "7"})))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_more_specific_wins")
