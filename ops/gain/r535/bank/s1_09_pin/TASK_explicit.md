# Task

Keep a value inside a permitted window.

Given a value and the two edges of the window, give back the value itself when
it already sits inside the window, and otherwise give back whichever edge it
has passed.

The value is the first argument, then the lower edge, then the upper edge.

## Interface

    pin(x, low, high) -> number

Write the code in a file called `solution.py` in this directory.
Nothing else is needed and nothing else is read.
