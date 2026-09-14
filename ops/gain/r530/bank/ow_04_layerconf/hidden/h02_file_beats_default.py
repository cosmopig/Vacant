# anchor_kind: contract
# anchor: Precedence is env over file over default.
# derivation: with no environment variable in play the file still has to beat the
# baked-in value.


def run(solution):
    defaults = {"timeout": 30}
    file_text = "timeout = 5\n"
    config = solution.load(defaults, file_text, {})
    got = (config.get("timeout"), config.source("timeout"))
    assert got == (5, "file"), "args=%r got=%r want=%r" % (file_text, got, (5, "file"))
