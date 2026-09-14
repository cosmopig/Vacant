"""Reference solution for ow_17_diffpatch (gauge only; never enters a workspace)."""

KEYS = {"start", "old", "new"}


def common_pairs(old, new):
    """Index pairs of a longest common subsequence, walked from the front.

    Walking forward and taking the diagonal whenever two lines agree is what keeps
    an unchanged line out of the front of a piece.
    """
    rows, columns = len(old), len(new)
    table = [[0] * (columns + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(columns - 1, -1, -1):
            if old[i] == new[j]:
                table[i][j] = table[i + 1][j + 1] + 1
            else:
                table[i][j] = max(table[i + 1][j], table[i][j + 1])
    pairs = []
    i = j = 0
    while i < rows and j < columns:
        if old[i] == new[j]:
            pairs.append((i, j))
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def trim(start, removed, added):
    """Drop lines that agree at either edge; they did not change."""
    while removed and added and removed[0] == added[0]:
        removed, added = removed[1:], added[1:]
        start += 1
    while removed and added and removed[-1] == added[-1]:
        removed, added = removed[:-1], added[:-1]
    if not removed and not added:
        return None
    return {"start": start, "old": removed, "new": added}


def diff(old, new):
    pieces = []
    cursor_old = cursor_new = 0
    for stop_old, stop_new in list(common_pairs(old, new)) + [(len(old), len(new))]:
        if stop_old > cursor_old or stop_new > cursor_new:
            piece = trim(cursor_old, list(old[cursor_old:stop_old]), list(new[cursor_new:stop_new]))
            if piece is not None:
                pieces.append(piece)
        cursor_old, cursor_new = stop_old + 1, stop_new + 1
    return pieces


def check(hunks, length):
    reach = 0
    for hunk in hunks:
        if not isinstance(hunk, dict) or set(hunk) != KEYS:
            raise ValueError("a piece must be a dict with exactly start, old and new: %r" % (hunk,))
        start = hunk["start"]
        if isinstance(start, bool) or not isinstance(start, int):
            raise ValueError("a piece's start must be a whole number: %r" % (start,))
        removed, added = hunk["old"], hunk["new"]
        if not isinstance(removed, list) or not isinstance(added, list):
            raise ValueError("a piece's old and new must both be lists: %r" % (hunk,))
        if not removed and not added:
            raise ValueError("a piece at %r is empty on both sides" % (start,))
        if start < reach:
            raise ValueError("pieces are out of order or overlap at %r" % (start,))
        if start + len(removed) > length:
            raise ValueError("a piece at %r reaches past the end of the text" % (start,))
        reach = start + len(removed)


def apply(old, hunks):
    check(hunks, len(old))
    out = []
    cursor = 0
    for hunk in hunks:
        start, removed, added = hunk["start"], hunk["old"], hunk["new"]
        out.extend(old[cursor:start])
        found = list(old[start:start + len(removed)])
        if found != list(removed):
            raise ValueError("piece at %d expected %r but the text holds %r"
                             % (start, list(removed), found))
        out.extend(added)
        cursor = start + len(removed)
    out.extend(old[cursor:])
    return out
