# anchor_kind: contract
# anchor: ordered by `start`, with at least one unchanged line between the end of
# one piece and the start of the next
# derivation: over a version with several scattered edits the pieces come back in
# order and never touch each other.


def run(solution):
    old = ["x%d" % index for index in range(20)]
    new = list(old)
    for index in (1, 5, 6, 13, 18):
        new[index] = "EDIT%d" % index
    pieces = solution.diff(old, new)
    reach = -1
    for piece in pieces:
        assert piece["start"] > reach, (
            "args=%r got=%r want=%r" % ("five scattered edits", piece["start"],
                                        "after the previous piece plus a gap"))
        reach = piece["start"] + len(piece["old"])
    assert solution.apply(old, pieces) == new, (
        "args=%r got=%r want=%r" % ("five scattered edits", solution.apply(old, pieces), new))
