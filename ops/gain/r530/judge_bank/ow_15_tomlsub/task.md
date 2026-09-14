# Goal

A client keeps their service settings in a small text format that looks like TOML
but is only the part of it they actually use. They need to read those files into
ordinary Python data, and to write the data back out so that a person can still
edit it by hand afterwards.

The values they use are text, whole numbers, decimals, true and false, and lists of
one of those. A list that mixes kinds is a mistake. Settings are grouped under
headings, and headings can be nested with dots.

Half of every file is comments, and a `#` inside a piece of text is not a comment.
Text sometimes has to contain quotes, tabs and line breaks, written with a
backslash.

The same setting written twice in one group, or the same heading opened twice, is a
mistake they want caught. Every mistake has to say which line it is on, because
these files are edited by hand and the file is the only thing they can look at.

Writing the data out and reading it back has to give the same data, and writing out
what was just read has to give the same text, so the format can sit in version
control without churning.

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
