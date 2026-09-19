# Task

`wrap(s, width)` breaks a line of text so that no piece comes out
longer than `width` characters, breaking between words. It gives the pieces
back in order, gathered in one list.

Words are separated by whitespace on the way in and by a single space inside a
piece. The text is a log message, and log messages contain identifiers that
nobody chose for their brevity.

## Details

- a word longer than width is never cut: it gets a piece to itself.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
