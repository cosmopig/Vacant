# Contract

    solution.parse(text: str) -> dict
    solution.dumps(data: dict) -> str

- A name -- a key, or one part of a heading -- is one or more characters from
  letters, digits, `_` and `-`.
- A line is blank, a comment, a heading `[a]` or `[a.b]`, or `name = value`.
  Everything from a `#` that is not inside text to the end of the line is a
  comment.
- The values are: `"text"`, in which `\"`, `\\`, `\n` and `\t` are the only
  escapes; a whole number written `-?digits`; a decimal written `-?digits.digits`;
  `true`; `false`; and a list `[v, v, v]` whose items are all of the same kind and
  are never lists themselves. `[]` is an empty list.
- A heading opens a group: the names after `[a.b]` live in `data["a"]["b"]`. Names
  before the first heading live at the top level.
- `parse` raises `ValueError` whose message begins `line <N>: `, with `N` the
  1-based line number, for anything it cannot read, for a name used twice in one
  group, and for a heading opened twice.
- `dumps` writes the top-level names first in name order, then each heading in
  name order with its own names in name order, and puts one blank line before each
  heading.
- `dumps` writes every setting on a line of its own as `name = value`, with exactly
  one space on each side of the `=`, and every heading on a line of its own.
- `dumps` raises `ValueError` for data it cannot write: a value of some other type,
  a list whose items are not all the same kind, a list inside a list, or a name
  outside the allowed characters.
- `parse(dumps(x))` gives back `x`, and `dumps(parse(dumps(x)))` gives back the
  same text.
