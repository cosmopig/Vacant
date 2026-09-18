# Task

`truncate(s, n)` shortens a piece of text so that it fits a column
`n` characters wide, marking that it was shortened by putting an ellipsis of
three dots at the end. Text that already fits is given back untouched.

The column is part of a fixed-width table, and the table's borders line up.

## Details

- the three dots count towards n, so the answer is never longer than n.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
