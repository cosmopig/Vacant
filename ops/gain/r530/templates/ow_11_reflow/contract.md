# Contract

    solution.reflow(text: str, width: int) -> str

- Width is display width: a character whose East Asian Width is Wide or Fullwidth
  counts as 2, every other character counts as 1.
- A blank line is a line holding nothing but whitespace. It is emitted as an empty
  line, and a run of blank lines keeps its length.
- A paragraph is a run of consecutive non-blank lines. A line whose first non-blank
  characters are a bullet marker -- `- `, `* `, or digits followed by `. ` --
  starts a new paragraph.
- Within a paragraph, runs of spaces and tabs separate words and are replaced by a
  single space.
- The first line of a paragraph keeps the indentation it had. Continuation lines
  repeat that indentation, except in a bullet paragraph, where they are indented to
  the first character after the marker.
- Lines are filled greedily up to `width` columns, counting the indentation.
- A break may fall between any two characters when at least one of them is wide,
  and no space is inserted at such a break.
- A piece that does not fit even on a line of its own is not split: it takes a line
  of its own and overflows it.
- No output line ends in a space.
- Everything inside a fenced code block opened and closed by three backticks is
  emitted unchanged, and so are the fence lines themselves.
- The presence or absence of a final newline is unchanged.
- `width <= 0` raises `ValueError`.
