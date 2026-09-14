# Goal

A client writes notes in plain text and wants them wrapped to a fixed width for
reading in a terminal. Their notes have indented blocks, bullet lists whose
continuation lines should line up under the text and not under the bullet, code
fenced off with backticks that must not be touched, and a lot of Chinese.

Chinese takes two columns per character in their terminal, and unlike English it
can be broken between any two characters without a space appearing at the break.

Blank lines are how they separate thoughts, so however many there were is however
many they want back. Each bullet in a list is its own thought and must not be
glued onto the one above it.

Now and then a note contains something with no spaces in it that is simply longer
than the width -- a URL, a long path -- and they would rather it stick out than be
chopped in half. A width that makes no sense should be refused.
