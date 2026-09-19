# Task

`mask(s, keep)` hides most of a piece of text, leaving `keep` of its
characters readable and replacing every other character with one single mask
character.

It is used on card numbers and account references in a support console, where
agents read the part back to the customer to confirm which card they are
looking at. `keep` comes from a policy file and is sometimes larger than the
text itself.

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
