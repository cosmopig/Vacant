# Task

`size_label(n)` turns a count of bytes into a short label for a user
interface, using the units B, KB, MB and GB and stopping at the largest unit
the number reaches.

The labels sit in a column next to each other in a file listing, so they are
meant to line up and read consistently.

## Details

- the step between units is 1024;
- above B the number takes one decimal place;
- there is a single space between the number and the unit.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
