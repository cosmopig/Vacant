# anchor_kind: contract
# anchor: may only appear as the last segment
# derivation: a rest-of-path capture in the middle is a malformed pattern and is
# rejected where it is written.


def run(solution):
    router = solution.Router()
    try:
        router.add("/files/{rest:*}/download", "broken")
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r"
                         % ("/files/{rest:*}/download", "no error", "ValueError"))
