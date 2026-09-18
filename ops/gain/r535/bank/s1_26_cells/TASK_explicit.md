# Task

Take one line of comma-separated text and give back its fields in
order, with any spaces around each field removed.

There are no quoted fields and no escaped commas, so every comma separates.
A line with nothing in it has one field, and that field is text with nothing
in it.

## Interface

    cells(line) -> list[str]

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
