# Task

`strip_comments(text)` removes everything from a hash character to
the end of the line it sits on, and gives back the remaining text.

The text is a configuration file, and the tool that reads the result reports
problems by line number, so those numbers have to keep pointing at the same
places. Nobody wants the diff to show whitespace that used to be in front of
a comment.

## Details

- a line whose whole content was a comment stays, as a line with nothing in it;
- trailing spaces are removed from every line.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
