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
