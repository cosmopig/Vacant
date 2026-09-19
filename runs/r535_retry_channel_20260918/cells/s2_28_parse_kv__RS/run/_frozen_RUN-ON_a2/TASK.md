# Task

`parse_kv(line)` reads a settings line of name=value pairs separated
by semicolons and gives back the lookup from name to value, both kept as text
with the spaces around them removed. A stretch between two semicolons with
nothing in it is skipped.

Lines are edited by hand, so both the same name written twice and a pair with
its equals sign missing turn up in real files.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
