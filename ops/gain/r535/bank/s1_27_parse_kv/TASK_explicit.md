# Task

Read a settings line made of name-and-value pairs.

Pairs are separated by semicolons. Inside a pair the name comes before an
equals sign and the value after it. Spaces around a name or a value are not
part of it. A stretch between two semicolons with nothing in it is skipped.

Build the lookup from name to value, both kept as text. When the same name
appears more than once, the later one wins.

## Interface

    parse_kv(line) -> dict[str, str]

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
