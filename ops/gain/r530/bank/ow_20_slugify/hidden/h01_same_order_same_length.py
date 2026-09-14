# anchor_kind: goal
# anchor: one slug per title, in the same order as the titles they handed in
# derivation: the slug for a title stays at that title's index, whatever the other
# titles in the batch are.


def run(solution):
    titles = ["Zebra Report", "Apple Notes", "Marker Title", "Banana Split"]
    got = solution.slugify(titles)
    assert len(got) == 4, "args=%r got=%r want=%r" % (titles, got, "four slugs")
    assert "marker" in got[2], "args=%r got=%r want=%r" % (titles, got[2], "the marker title's slug")
    assert "zebra" in got[0] and "banana" in got[3], (
        "args=%r got=%r want=%r" % (titles, got, "order kept"))
