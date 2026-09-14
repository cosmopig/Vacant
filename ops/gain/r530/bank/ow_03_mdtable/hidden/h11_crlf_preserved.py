# anchor_kind: goal
# anchor: files saved on Windows must come back with the line endings they arrived
# with
# derivation: a CRLF document must still be CRLF afterwards, and must not have
# gained a lone LF anywhere.


def run(solution):
    text = "| a | bb |\r\n| --- | --- |\r\n| 1 | 2 |\r\n"
    got = solution.realign(text)
    assert got.count("\r\n") == 3, "args=%r got=%r want=%r" % (text, got.count("\r\n"), 3)
    assert got.count("\n") == got.count("\r\n"), (
        "args=%r got=%r want=%r" % (text, got, "no bare LF"))
