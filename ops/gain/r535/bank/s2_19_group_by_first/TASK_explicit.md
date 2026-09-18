# Task

`group_by_first(words)` sorts words into a lookup keyed by the letter
each one starts with, keeping each group in the order the words arrived.

The words are read out of a file one per line, so what arrives is whatever the
file held, including the odd line that held nothing.

## Details

- the key is the lower-cased first letter;
- a word with nothing in it is dropped.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
