"""Known-bad B: the closest near miss.

It finds the first and the last line that differ and calls everything between them
one piece, which is right for a single edit and wrong for two. Apply checks that the
piece fits, which is the dangerous case, but it patches the caller's own list in
place and never looks at whether the pieces are in order or well formed.
"""


def diff(old, new):
    old, new = list(old), list(new)
    if old == new:
        return []
    first = 0
    while first < len(old) and first < len(new) and old[first] == new[first]:
        first += 1
    back = 0
    while (back < len(old) - first and back < len(new) - first
           and old[len(old) - 1 - back] == new[len(new) - 1 - back]):
        back += 1
    return [{"start": first,
             "old": old[first:len(old) - back],
             "new": new[first:len(new) - back]}]


def apply(old, hunks):
    for hunk in hunks:
        start, removed, added = hunk["start"], hunk["old"], hunk["new"]
        found = old[start:start + len(removed)]
        if list(found) != list(removed):
            raise ValueError("piece at %d does not fit" % start)
        old[start:start + len(removed)] = list(added)
    return old
