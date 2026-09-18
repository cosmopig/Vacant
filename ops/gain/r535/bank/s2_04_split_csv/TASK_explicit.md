# Task

`split_csv(line)` takes one line of comma-separated text and gives
back its fields in order as a list of strings.

There are no quoted fields and no escaped commas, so every comma separates.
The lines come straight off a file that sometimes has a blank line in it.

## Details

- each field has the spaces around it removed;
- a line with nothing in it gives back [], not a list holding one empty string.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
