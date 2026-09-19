# Task

`chunks(xs, n)` cuts a list into consecutive pieces of size n, in
order, and gives the pieces back gathered in one list. The last piece is
whatever is left over and may be shorter than the others.

The size arrives from a command line flag, and callers do not always pass
something sensible.

## Details

- an n that is not positive raises ValueError.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
