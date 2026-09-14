# Goal

A client writes notes in plain text and wants them wrapped to a fixed width for
reading in a terminal. Their notes have indented blocks, bullet lists whose
continuation lines should line up under the text and not under the bullet, code
fenced off with backticks that must not be touched, and a lot of Chinese.

Chinese takes two columns per character in their terminal, and unlike English it
can be broken between any two characters without a space appearing at the break.

Blank lines are how they separate thoughts, so however many there were is however
many they want back. Each bullet in a list is its own thought and must not be
glued onto the one above it.

Now and then a note contains something with no spaces in it that is simply longer
than the width -- a URL, a long path -- and they would rather it stick out than be
chopped in half. A width that makes no sense should be refused.

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
