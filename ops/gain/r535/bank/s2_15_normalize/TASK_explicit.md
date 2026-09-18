# Task

`normalize(p)` tidies a forward-slash path: a run of separators
becomes a single separator.

The paths are joined together by other code that is careless about whether a
piece already ends in a separator, so what arrives here has separators in
places nobody meant to put one.

## Details

- a separator at the very end is removed, unless the whole path is that separator.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
