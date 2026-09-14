"""Known-bad A: replace the whole file and trust whatever it is handed.

One piece covering everything, and an apply that splices without checking that the
piece belongs to this version of the text.
"""


def diff(old, new):
    if list(old) == list(new):
        return []
    return [{"start": 0, "old": list(old), "new": list(new)}]


def apply(old, hunks):
    out = list(old)
    for hunk in hunks:
        start = hunk["start"]
        out[start:start + len(hunk["old"])] = list(hunk["new"])
    return out
