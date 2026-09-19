# Task

`flatten(xs)` gives back a single list gathered from the entries of
the list it is handed.

The list is the result of collecting answers from several workers: a worker
that had several answers put a list in, and a worker that had exactly one put
the answer itself in.

## Details

- only one level is undone: a list inside an inner list stays a list.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
