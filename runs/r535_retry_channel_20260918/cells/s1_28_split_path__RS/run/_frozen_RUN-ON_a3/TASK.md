# Task

Break a file path into three pieces: the folder part in front of the
last separator, the file's own name without its extension, and the extension
without the dot in front of it.

The separator is a forward slash. A path with no folder part has a folder
piece with nothing in it; a name with no dot has an extension with nothing in
it; when there is more than one dot, only the last one starts the extension.

The three pieces come back together in one object.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
