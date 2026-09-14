# Goal

A client reviews changes to plain text files by hand. They want to see what changed
between two versions as a list of pieces, and they want to be able to take that
list and put it back onto the old version to get the new one.

They want the difference described as separate pieces, one per place that changed,
so that a reviewer sees the two lines that moved rather than one block covering
everything between them. A piece must not carry lines that did not change: not at
its start, not at its end. A file that did not change at all produces no pieces.

Applying a list of pieces to a version they do not fit is the dangerous case --
someone edited the file in between -- and has to be refused loudly rather than
producing a mangled file. The same goes for a list of pieces that is out of order,
that overlaps itself, or that is simply malformed.

Applying must not touch what it was given, because they keep the old version
around. Files with many identical lines are common in their data, and going out and
back has to survive them.

# Contract

    solution.diff(old: list[str], new: list[str]) -> list[dict]
    solution.apply(old: list[str], hunks: list[dict]) -> list[str]

- A piece is a dict with exactly the keys `start`, `old` and `new`. `start` is a
  0-based index into the old list; `old` is the run of lines being replaced,
  beginning at `start`; `new` is what replaces them. Either side may be empty, but
  not both.
- `diff` returns the pieces ordered by `start`, with at least one unchanged line
  between the end of one piece and the start of the next, and with no piece
  beginning or ending with a line that is the same on both of its sides.
- `apply(old, diff(old, new))` equals `new`, for any two lists.
- `apply` returns a new list and changes neither of its arguments.
- `apply` raises `ValueError` when a piece's `old` is not what the old list holds
  at `start`, when the pieces are out of order or overlap, when a piece reaches
  past the end of the old list, when a piece is empty on both sides, or when a
  piece is not a dict with exactly those three keys.
