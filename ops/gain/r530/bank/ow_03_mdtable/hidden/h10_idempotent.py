# anchor_kind: goal
# anchor: running it twice must produce the same file as running it once
# derivation: the pre-commit hook would loop forever otherwise, so the second pass
# has to be a no-op on the first pass's output.


def run(solution):
    text = "| 名稱 |n|\n|:--|--:|\n|甲|1|\n|lengthy name|22|\n\nnot a table\n"
    once = solution.realign(text)
    twice = solution.realign(once)
    assert once == twice, "args=%r got=%r want=%r" % (text, twice, once)
