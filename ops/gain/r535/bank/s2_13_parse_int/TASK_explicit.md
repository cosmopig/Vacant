# Task

`parse_int(s)` reads a whole number out of a piece of text and gives
it back as a number. Text that does not spell a whole number is rejected with
a ValueError.

The caller is a configuration reader, and the values it hands over have
already been through several layers that are not fussy about what they pass
along.

## Details

- something that is not text at all raises TypeError, not ValueError.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
