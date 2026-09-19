# Task

Compress a piece of text by replacing each run of one repeated
character with that character together with how many times it repeated in a
row.

The runs come back in order, each one as a pair holding the character first
and the count second. A pair here is the immutable kind.

## Interface

    rle(s) -> list[tuple[str, int]]

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
