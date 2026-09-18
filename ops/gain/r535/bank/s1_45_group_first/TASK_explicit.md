# Task

Sort a list of words into groups according to the letter each one
starts with.

The letter used for a group is written in lower case. Inside a group the words
keep the order they were handed in, and they keep their own spelling exactly.
The groups come back as a lookup from the letter to the words. No word handed
in is ever without characters.

## Interface

    group_first(words) -> dict[str, list[str]]

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
