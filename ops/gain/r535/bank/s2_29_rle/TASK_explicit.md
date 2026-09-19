# Task

`rle(s)` compresses a piece of text by reporting each run of one
repeated character as that character together with how long the run was, in
order.

The result is handed to code that puts the runs into a table and then hashes
the table, so the runs have to come back as values that cannot be changed
afterwards.

## Details

- each run comes back as a tuple, not as a list.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
