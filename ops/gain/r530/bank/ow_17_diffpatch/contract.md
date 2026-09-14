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
