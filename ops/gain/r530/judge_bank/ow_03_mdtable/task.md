# Goal

A client's markdown documents are full of tables whose columns do not line up,
and some of the cells contain Chinese and Japanese text. They want one pass over
a whole document that makes every table's columns line up when read in a plain
text editor, and leaves everything that is not a table exactly as it was.

Their documents also contain pipe characters that are not column separators: some
are escaped, some sit inside inline code, and some are inside fenced code blocks
that happen to show a table. None of those may be treated as structure.

The tool is going to run in a pre-commit hook, so running it twice must produce
the same file as running it once, and files saved on Windows must come back with
the line endings they arrived with.

Their tables are also sloppy: some rows have more cells than the header, some
cells are empty, and some rows are missing the pipes at the start and end. A
document with no table in it at all must come back byte for byte.

# Contract

    solution.realign(text: str) -> str

- A column separator is a `|` that is neither preceded by a backslash nor inside a
  span delimited by backticks.
- A separator row is a row whose cells all match `:?-+:?`.
- A table is a run of consecutive lines whose first line contains a column
  separator and whose second line is a separator row; it ends at the first line
  that is blank or holds no column separator.
- Alignment is computed from display width: a character whose East Asian Width is
  Wide or Fullwidth counts as 2, every other character counts as 1.
- Every rendered row begins with `| ` and ends with ` |`, and neighbouring cells
  are joined by ` | `. Cell text is stripped of surrounding whitespace and then
  padded on the right to the column's width.
- A column's width is the widest of its non-separator cells, and never less than 3.
- A separator cell keeps the alignment markers it had -- `---`, `:---`, `---:` or
  `:---:` -- and its dashes are stretched or shortened so that the cell fills the
  column width.
- The number of columns is the largest cell count of any row in the table; shorter
  rows are padded with empty cells.
- Lines that are not part of a table are emitted unchanged, and so is every line
  inside a fenced code block opened by three backticks or three tildes.
- Each line keeps the line ending it arrived with, and the presence or absence of
  a final newline is unchanged.
