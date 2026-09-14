# anchor_kind: contract
# anchor: Two patterns that differ only in their parameter names are the same
# pattern. Registering the second one raises `ValueError` from `add`.
# derivation: the parameter name is not part of what makes a pattern distinct, so
# the second registration is a collision.


def run(solution):
    router = solution.Router()
    router.add("/items/{id}", "first")
    try:
        router.add("/items/{item_id}", "second")
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r"
                         % ("/items/{item_id} after /items/{id}", "no error", "ValueError"))
